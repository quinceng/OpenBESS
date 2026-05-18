"""Commercial BESS modelling branch.

This namespace is separate from the residential branch and from the central
utility-scale optimiser internals. It gives commercial modelling a clean place
to grow without inheriting household defaults.
"""

from gb_bess_revenue_stack.commercial.models import CommercialBessSystem

__all__ = ["CommercialBessSystem"]
