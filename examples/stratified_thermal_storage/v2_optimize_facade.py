import os
import sys
import pandas as pd
import numpy as np

from oemof.thermal import facades

# import functions to compare lp-files of new example with old one.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'tests')))
from test_constraints import compare_lp_files  # noqa

from oemof.thermal.stratified_thermal_storage import (  # noqa
    calculate_storage_u_value,
)

from oemof.solph import Source, Sink, Bus, Flow, Model, EnergySystem  # noqa

data_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'storage_specification.csv')

input_data = pd.read_csv(data_path, index_col=0, header=0)['var_value']

u_value = calculate_storage_u_value(
    input_data['s_iso'],
    input_data['lamb_iso'],
    input_data['alpha_inside'],
    input_data['alpha_outside'])


def print_parameters():
    parameter = {
        'U-value [W/(m2*K)]': u_value,
    }

    dash = '-' * 50

    print(dash)
    print('{:>32s}{:>15s}'.format('Parameter name', 'Value'))
    print(dash)

    for name, param in parameter.items():
        print('{:>32s}{:>15.5f}'.format(name, param))

    print(dash)


print_parameters()

# Set up an energy system model
solver = 'cbc'
periods = 100
datetimeindex = pd.date_range('1/1/2019', periods=periods, freq='H')
demand_timeseries = np.zeros(periods)
demand_timeseries[-5:] = 1
heat_feedin_timeseries = np.zeros(periods)
heat_feedin_timeseries[:10] = 1

energysystem = EnergySystem(timeindex=datetimeindex)

bus_heat = Bus(label='bus_heat')

heat_source = Source(
    label='heat_source',
    outputs={bus_heat: Flow(
        nominal_value=1,
        actual_value=heat_feedin_timeseries,
        fixed=True)})

shortage = Source(
    label='shortage',
    outputs={bus_heat: Flow(variable_costs=1e6)})

excess = Sink(
    label='excess',
    inputs={bus_heat: Flow()})

heat_demand = Sink(
    label='heat_demand',
    inputs={bus_heat: Flow(
        nominal_value=1,
        actual_value=demand_timeseries,
        fixed=True)})

thermal_storage = facades.StratifiedThermalStorage(
    label='thermal_storage',
    bus=bus_heat,
    diameter=input_data['diameter'],
    height=input_data['height'],
    temp_h=input_data['temp_h'],
    temp_c=input_data['temp_c'],
    temp_env=input_data['temp_env'],
    u_value=u_value,
    min_storage_level=input_data['min_storage_level'],
    max_storage_level=input_data['max_storage_level'],
    capacity=input_data['maximum_heat_flow_charging'],
    efficiency=1,
    marginal_cost=0.0001
)

energysystem.add(bus_heat, heat_source, shortage, excess, heat_demand, thermal_storage)

# create and solve the optimization model
optimization_model = Model(energysystem)
optimization_model.write('storage_model_facades.lp', io_options={'symbolic_solver_labels': True})

with open('storage_model_facades.lp') as generated_file:
    with open('storage_model.lp') as expected_file:
        compare_lp_files(generated_file, expected_file)
