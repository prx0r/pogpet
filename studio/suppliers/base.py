"""Supplier adapter contract. Every supplier (JLC, LCSC, Printie, PCBWay...) implements this.
estimate() is offline + free and always works. quote() hits the supplier (free, needs creds).
order() spends money: disabled unless ODDHOBB_ENABLE_ORDERS=1 AND an approval token from the human is passed."""
import os
from dataclasses import dataclass, field, asdict

@dataclass
class Money:
    amount: float | None
    currency: str = 'USD'
    basis: str = 'estimate'      # estimate | quote | invoice
    ref: str | None = None
    note: str = ''

@dataclass
class Line:
    supplier: str
    service: str                 # tdp | pcb | pcba | parts | fdm ...
    item: str
    qty: int
    unit: Money
    total: Money
    meta: dict = field(default_factory=dict)

class Supplier:
    id = 'base'
    services: list[str] = []
    def configured(self) -> bool: return False
    def estimate(self, service: str, spec: dict) -> Line: raise NotImplementedError
    def upload(self, service: str, path: str) -> dict: raise NotImplementedError
    def quote(self, service: str, spec: dict) -> Line: raise NotImplementedError
    def order(self, service: str, spec: dict, approval: str | None = None) -> dict:
        if os.environ.get('ODDHOBB_ENABLE_ORDERS') != '1' or not approval:
            raise PermissionError('orders disabled: needs ODDHOBB_ENABLE_ORDERS=1 and a human approval token')
        raise NotImplementedError

def as_dict(x): return asdict(x)
