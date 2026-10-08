"""PRABHAT: tracked-object extreme-weather anomaly detection with runtime gates.

The pipeline runs in stages, named S0 to S8 throughout the code:

    S0  input ensemble          prabhat.ensemble
    S1  anomaly tube + EFI      prabhat.tracking, prabhat.efi
    S2  analogue retrieval      prabhat.analogues
    S4  5 km downscaling        prabhat.downscale
    S5  runtime gates           prabhat.gates
    S6  user-class alerts       prabhat.alerts   (S6b: hysteresis / churn)
    S7  API + dashboard         prabhat.api, dashboard/
    S8  verification ledger     prabhat.ledger
"""

__version__ = "0.1.0"
