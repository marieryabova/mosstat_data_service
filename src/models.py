from dataclasses import dataclass

@dataclass
class Indicator:
    id: str
    url: str
    section: str
    filename: str