from config.settings import ROUTING_WEIGHTS
from src.routing.shelter_assignment import Shelter, ShelterStatus, assign_best, assign_nearest


def _setup():
    shelters = [Shelter(0, 10, 0, 0, capacity=100, occupancy=100, status=ShelterStatus.FULL),
                Shelter(1, 11, 0, 0, capacity=100),
                Shelter(2, 12, 0, 0, capacity=100, status=ShelterStatus.UNSAFE)]
    dist = {10: 1.0, 11: 5.0, 12: 2.0}
    paths = {10: [0, 10], 11: [0, 11], 12: [0, 12]}
    return shelters, dist, paths, {0: 0, 1: 0, 2: 0}


def test_baseline_picks_nearest_even_if_full_or_unsafe():
    s, d, p, _ = _setup()
    assert assign_nearest(s, d, p)[0] == 0


def test_proposed_skips_full_and_unsafe():
    s, d, p, r = _setup()
    assert assign_best(s, d, p, 25, r, None, ROUTING_WEIGHTS)[0] == 1


def test_proposed_respects_reservations():
    s, d, p, r = _setup()
    r[1] = 80                      # 80 of 100 already promised to others
    assert assign_best(s, d, p, 25, r, None, ROUTING_WEIGHTS) is None


def test_own_reservation_not_double_counted():
    s, d, p, r = _setup()
    r[1] = 100                     # fully reserved, but 25 of it is this agent's
    assert assign_best(s, d, p, 25, r, 1, ROUTING_WEIGHTS)[0] == 1


def test_remaining_capacity():
    assert Shelter(0, 1, 0, 0, capacity=500, occupancy=320).remaining_capacity == 180
