# src/events/management/commands/bootstrap_helpers/base.py
"""Base classes and shared state for bootstrap helpers."""

from dataclasses import dataclass, field

from faker import Faker

from accounts.models import RevelUser
from common.models import Tag
from events import models as events_models
from geo.models import City


@dataclass
class BootstrapState:
    """Shared state container for bootstrap process."""

    fake: Faker = field(default_factory=lambda: Faker("en_US"))
    users: dict[str, RevelUser] = field(default_factory=dict)
    orgs: dict[str, events_models.Organization] = field(default_factory=dict)
    venues: dict[str, events_models.Venue] = field(default_factory=dict)
    events: dict[str, events_models.Event] = field(default_factory=dict)
    event_series: dict[str, events_models.EventSeries] = field(default_factory=dict)
    tags: dict[str, Tag] = field(default_factory=dict)
    cities: dict[str, City] = field(default_factory=dict)

    def fake_address(self) -> str:
        """Generate a clean fake address."""
        return " ".join(self.fake.address().split())

    def load_cities(self) -> None:
        """Load Rio de Janeiro cities/bairros for events."""
        self.cities["copacabana"] = City.objects.get(name="Copacabana")
        barra_da_tijuca = City.objects.filter(name="Barra da Tijuca").first()
        lapa = City.objects.filter(name="Lapa").first()
        tijuca = City.objects.filter(name="Tijuca").first()
        niteroi = City.objects.filter(name="Niterói").first()

        assert barra_da_tijuca is not None, "Barra da Tijuca city not found"
        assert lapa is not None, "Lapa city not found"
        assert tijuca is not None, "Tijuca city not found"
        assert niteroi is not None, "Niterói city not found"

        self.cities["barra_da_tijuca"] = barra_da_tijuca
        self.cities["lapa"] = lapa
        self.cities["tijuca"] = tijuca
        self.cities["niteroi"] = niteroi
