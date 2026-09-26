import React, { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import { feature } from 'topojson-client'
import land from 'world-atlas/land-50m.json'
import countries from 'world-atlas/countries-50m.json'

import { EFI_RAMP, RAMP } from '../api.js'

/* DESIGN §5-S7 dashboard items 1 and 2: tube polygons animating over lead
   time, with the exceedance raster inside the tube.

   The basemap is bundled, not tiled. Natural Earth geometry ships in the
   world-atlas package and is converted here at runtime, so the map draws with
   the network unplugged — the same offline guarantee the pipeline gives
   (DESIGN §13.6). A tile-server basemap would have quietly broken it. */

const LAND = feature(land, land.objects.land)
const BORDERS = feature(countries, countries.objects.countries)

const EMPTY = { type: 'FeatureCollection', features: [] }

/* Probability raster as graduated cells. A 5 km field over a tube is a few
   thousand cells — well within what MapLibre draws as GeoJSON polygons, and it
   keeps the colour ramp in one place rather than baking a PNG. */
function rasterToGeoJSON(ras, leadIndex) {
  if (!ras) return EMPTY
  const plane = ras.values[leadIndex]
  if (!plane) return EMPTY
  const { lat, lon } = ras
  const dLat = lat.length > 1 ? Math.abs(lat[1] - lat[0]) : 0.25
  const dLon = lon.length > 1 ? Math.abs(lon[1] - lon[0]) : 0.25
  const features = []
  for (let i = 0; i < lat.length; i++) {
    for (let j = 0; j < lon.length; j++) {
      const p = plane[i][j]
      if (p <= 0.02) continue          // below this it is visual noise
      const y = lat[i], x = lon[j]
      features.push({
        type: 'Feature',
        properties: { p },
        geometry: {
          type: 'Polygon',
          coordinates: [[
            [x - dLon / 2, y - dLat / 2],
            [x + dLon / 2, y - dLat / 2],
            [x + dLon / 2, y + dLat / 2],
            [x - dLon / 2, y + dLat / 2],
            [x - dLon / 2, y - dLat / 2],
          ]],
        },
      })
    }
  }
  return { type: 'FeatureCollection', features }
}

function tubeGeoJSON(tube, leadIndex) {
  if (!tube) return { box: EMPTY, track: EMPTY, head: EMPTY }
  const pt = tube.points[Math.min(leadIndex, tube.points.length - 1)]
  const [latMin, lonMin, latMax, lonMax] = pt.bbox

  const box = {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      properties: { confidence: pt.confidence },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [lonMin, latMin], [lonMax, latMin],
          [lonMax, latMax], [lonMin, latMax], [lonMin, latMin],
        ]],
      },
    }],
  }

  const track = {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      properties: {},
      geometry: {
        type: 'LineString',
        coordinates: tube.points.map((p) => [p.centroid_lon, p.centroid_lat]),
      },
    }],
  }

  const head = {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      properties: { lead: pt.lead_hour },
      geometry: { type: 'Point', coordinates: [pt.centroid_lon, pt.centroid_lat] },
    }],
  }

  return { box, track, head }
}

/* Step expression over the sequential ramp, kept in sync with styles.css. */
const RAMP_EXPR = [
  'step', ['get', 'p'],
  RAMP[0],
  1 / 6, RAMP[1],
  2 / 6, RAMP[2],
  3 / 6, RAMP[3],
  4 / 6, RAMP[4],
  5 / 6, RAMP[5],
]

/* EFI is signed, so its step expression is centred on zero. */
const EFI_EXPR = [
  'step', ['get', 'v'],
  EFI_RAMP[0],
  -0.6, EFI_RAMP[1],
  -0.3, EFI_RAMP[2],
  -0.15, EFI_RAMP[3],
  0.15, EFI_RAMP[4],
  0.3, EFI_RAMP[5],
  0.6, EFI_RAMP[6],
]

function efiToGeoJSON(efi, leadIndex) {
  if (!efi) return EMPTY
  const plane = efi.values[Math.min(leadIndex, efi.values.length - 1)]
  if (!plane) return EMPTY
  const { lat, lon } = efi
  const dLat = lat.length > 1 ? Math.abs(lat[1] - lat[0]) : 0.5
  const dLon = lon.length > 1 ? Math.abs(lon[1] - lon[0]) : 0.5
  const features = []
  for (let i = 0; i < lat.length; i++) {
    for (let j = 0; j < lon.length; j++) {
      const v = plane[i][j]
      if (Math.abs(v) < 0.15) continue      // below this it is not an anomaly
      const y = lat[i], x = lon[j]
      features.push({
        type: 'Feature',
        properties: { v },
        geometry: {
          type: 'Polygon',
          coordinates: [[
            [x - dLon / 2, y - dLat / 2], [x + dLon / 2, y - dLat / 2],
            [x + dLon / 2, y + dLat / 2], [x - dLon / 2, y + dLat / 2],
            [x - dLon / 2, y - dLat / 2],
          ]],
        },
      })
    }
  }
  return { type: 'FeatureCollection', features }
}

export default function MapView({ tube, raster, efi, layer, leadIndex, alertCentre, bbox }) {
  const container = useRef(null)
  const map = useRef(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (map.current) return
    map.current = new maplibregl.Map({
      container: container.current,
      style: {
        version: 8,
        sources: {},
        layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#e2ecf6' } }],
      },
      center: [85, 20],
      zoom: 4,
      attributionControl: false,
    })
    map.current.on('error', (e) => console.error('[maplibre]', e?.error?.message || e))
    map.current.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left')
    map.current.addControl(
      new maplibregl.AttributionControl({
        compact: true,
        customAttribution: 'Basemap: Natural Earth (public domain), bundled offline',
      }),
      'bottom-right',
    )

    map.current.on('load', () => {
      const m = map.current

      m.addSource('land', { type: 'geojson', data: LAND })
      m.addLayer({
        id: 'land',
        type: 'fill',
        source: 'land',
        paint: { 'fill-color': '#ebe6d9', 'fill-outline-color': '#c7bda5' },
      })

      m.addSource('borders', { type: 'geojson', data: BORDERS })
      m.addLayer({
        id: 'borders',
        type: 'line',
        source: 'borders',
        paint: { 'line-color': '#b6ac93', 'line-width': 0.8 },
      })

      m.addSource('prob', { type: 'geojson', data: EMPTY })
      m.addLayer({
        id: 'prob',
        type: 'fill',
        source: 'prob',
        paint: {
          'fill-color': RAMP_EXPR,
          // Low probabilities recede toward the surface; high ones read solid.
          'fill-opacity': ['interpolate', ['linear'], ['get', 'p'], 0.02, 0.15, 1, 0.82],
        },
      })

      m.addSource('efi', { type: 'geojson', data: EMPTY })
      m.addLayer({
        id: 'efi',
        type: 'fill',
        source: 'efi',
        layout: { visibility: 'none' },
        paint: {
          'fill-color': EFI_EXPR,
          'fill-opacity': ['interpolate', ['linear'], ['abs', ['get', 'v']],
                          0.15, 0.2, 1, 0.8],
        },
      })

      m.addSource('track', { type: 'geojson', data: EMPTY })
      m.addLayer({
        id: 'track',
        type: 'line',
        source: 'track',
        paint: {
          'line-color': '#b8461f',
          'line-width': 1.4,
          'line-dasharray': [3, 2],
          'line-opacity': 0.8,
        },
      })

      m.addSource('tube', { type: 'geojson', data: EMPTY })
      m.addLayer({
        id: 'tube-line',
        type: 'line',
        source: 'tube',
        paint: { 'line-color': '#c25a1e', 'line-width': 1.6 },
      })

      m.addSource('head', { type: 'geojson', data: EMPTY })
      m.addLayer({
        id: 'head-halo',
        type: 'circle',
        source: 'head',
        paint: {
          'circle-radius': 16,
          'circle-color': '#b8461f',
          'circle-opacity': 0.14,
        },
      })
      m.addLayer({
        id: 'head-dot',
        type: 'circle',
        source: 'head',
        paint: {
          'circle-radius': 4,
          'circle-color': '#c25a1e',
          'circle-stroke-width': 1,
          'circle-stroke-color': '#ffffff',
        },
      })

      m.addSource('alert', { type: 'geojson', data: EMPTY })
      m.addLayer({
        id: 'alert-pin',
        type: 'circle',
        source: 'alert',
        paint: {
          'circle-radius': 6,
          'circle-color': '#c23434',
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff',
        },
      })

      // Hover readout on the probability raster (dataviz: charts get a hover layer).
      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false })
      m.on('mousemove', 'prob', (e) => {
        m.getCanvas().style.cursor = 'crosshair'
        const p = e.features[0].properties.p
        popup
          .setLngLat(e.lngLat)
          .setHTML(
            `<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#1d1c18">
               <b style="font-size:15px">${(p * 100).toFixed(0)}%</b><br/>
               ${e.lngLat.lat.toFixed(2)}N ${e.lngLat.lng.toFixed(2)}E
             </div>`,
          )
          .addTo(m)
      })
      m.on('mouseleave', 'prob', () => {
        m.getCanvas().style.cursor = ''
        popup.remove()
      })

      m.resize()
      setReady(true)
    })
  }, [])

  // Fit to the case domain when it changes.
  useEffect(() => {
    if (!map.current || !bbox) return
    const fit = () => {
      const [latMin, lonMin, latMax, lonMax] = bbox
      map.current.fitBounds([[lonMin, latMin], [lonMax, latMax]], {
        padding: 60, duration: 900,
      })
    }
    if (ready) fit()
    else map.current.once('load', fit)
  }, [bbox, ready])

  // Push data on every lead-time step.
  useEffect(() => {
    const m = map.current
    if (!m || !ready) return
    const { box, track, head } = tubeGeoJSON(tube, leadIndex)
    m.getSource('tube')?.setData(box)
    m.getSource('track')?.setData(track)
    m.getSource('head')?.setData(head)
    m.getSource('prob')?.setData(
      layer === 'efi' ? EMPTY : rasterToGeoJSON(raster, leadIndex),
    )
    m.getSource('efi')?.setData(layer === 'efi' ? efiToGeoJSON(efi, leadIndex) : EMPTY)
    if (m.getLayer('efi')) {
      m.setLayoutProperty('efi', 'visibility', layer === 'efi' ? 'visible' : 'none')
    }
    m.getSource('alert')?.setData(
      alertCentre
        ? {
            type: 'FeatureCollection',
            features: [{
              type: 'Feature', properties: {},
              geometry: { type: 'Point', coordinates: [alertCentre[1], alertCentre[0]] },
            }],
          }
        : EMPTY,
    )
  }, [tube, raster, efi, layer, leadIndex, alertCentre, ready])

  return <div className="map" ref={container} />
}
