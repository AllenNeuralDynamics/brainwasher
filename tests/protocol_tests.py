#!/usr/bin/env/python3

import pytest
from brainwasher.protocol import Protocol
from io import StringIO
from pint import UnitRegistry

csv_str = \
    ('"Mix Speed",Chemicals,Solution,Duration\n'
     '100%,"THF, DCM","30% THF, 70% DCM", "1hr"\n'
     '100,"SBiP","100% SBiP", "2.5hr"')

test_csv = StringIO(csv_str)
protocol = Protocol(test_csv)
ureg = UnitRegistry()


def test_chemical_parsing():
    assert {"THF", "DCM", "SBiP"} == protocol.get_chemicals()


def test_chemical_parsing_single_row_many_entries():
    assert {"THF", "DCM"} == protocol.get_chemicals(step=0)


def test_chemical_parsing_single_row_single_entry():
    assert {"SBiP"} == protocol.get_chemicals(step=1)


def test_solution_parsing_simple():
    assert protocol.get_solution(step=0, max_volume_ul=10000) == {"THF": 3000,
                                                                  "DCM": 7000}
    assert protocol.get_solution(step=1, max_volume_ul=10000) == {"SBiP": 10000}


def test_step_count():
    assert protocol.step_count == 2


def test_get_mix_speed():
    assert protocol.get_mix_speed_percent(0) == 100
    assert protocol.get_mix_speed_percent(1) == 100
