"""
This example shows how to use the functions of the stratified thermal storage
module to specify a storage in an optimization with oemof.solph.
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from oemof.thermal.stratified_thermal_storage import (
    calculate_storage_u_value,
    calculate_storage_dimensions,
    calculate_capacities,
    calculate_losses,
)
from oemof.solph import Source, Sink, Bus, Flow, Model, EnergySystem
from oemof.solph.components import GenericStorage
import oemof.outputlib as outputlib


data_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'stratified_thermal_storage.csv')

input_data = pd.read_csv(data_path, index_col=0, header=0)['var_value']

u_value = calculate_storage_u_value(
    input_data['s_iso'],
    input_data['lamb_iso'],
    input_data['alpha_inside'],
    input_data['alpha_outside'])

volume, surface = calculate_storage_dimensions(
    input_data['height'],
    input_data['diameter']
)

nominal_storage_capacity = calculate_capacities(
    volume,
    input_data['temp_h'],
    input_data['temp_c'])

loss_rate, fixed_losses_relative, fixed_losses_absolute = calculate_losses(
    u_value,
    input_data['diameter'],
    input_data['temp_h'],
    input_data['temp_c'],
    input_data['temp_env'])

maximum_heat_flow_charging = 2
maximum_heat_flow_discharging = 2


def print_parameters():
    parameter = {
        'U-value [W/(m2*K)]': u_value,
        'Volume [m3]': volume,
        'Surface [m2]': surface,
        'Nominal storage capacity [MWh]': nominal_storage_capacity,
        'Max. heat flow charging [MW]': maximum_heat_flow_charging,
        'Max. heat flow discharging [MW]': maximum_heat_flow_discharging,
        'Loss rate [-]': loss_rate,
        'Fixed relative losses [-]': fixed_losses_relative,
        'Fixed absolute losses [MWh]': fixed_losses_absolute,
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

thermal_storage = GenericStorage(
    label='thermal_storage',
    inputs={bus_heat: Flow(
        nominal_value=maximum_heat_flow_charging)},
    outputs={bus_heat: Flow(
        nominal_value=maximum_heat_flow_discharging,
        variable_costs=0.0001
    )},
    nominal_storage_capacity=nominal_storage_capacity,
    min_storage_level=input_data['min_storage_level'],
    max_storage_level=input_data['max_storage_level'],
    loss_rate=loss_rate,
    fixed_losses_relative=fixed_losses_relative,
    fixed_losses_absolute=fixed_losses_absolute,
    inflow_conversion_factor=1.0,
    outflow_conversion_factor=1.0,
)

energysystem.add(bus_heat, heat_source, shortage, excess, heat_demand, thermal_storage)

# create and solve the optimization model
optimization_model = Model(energysystem)
optimization_model.write('storage_model.lp', io_options={'symbolic_solver_labels': True})
optimization_model.solve(solver=solver,
                         solve_kwargs={'tee': False, 'keepfiles': False})
# get results
results = outputlib.processing.results(optimization_model)
string_results = outputlib.processing.convert_keys_to_strings(results)
sequences = {k: v['sequences'] for k, v in string_results.items()}
df = pd.concat(sequences, axis=1)

# plot results
fig, (ax1, ax2) = plt.subplots(2, 1)

df[[('shortage', 'bus_heat', 'flow'),
    ('heat_source', 'bus_heat', 'flow'),
    ('thermal_storage', 'bus_heat', 'flow')]].plot.area(ax=ax1, stacked=True, color=['y', 'b', 'k'])

(-df[('bus_heat', 'thermal_storage', 'flow')]).plot.area(ax=ax1, color='g')

df[('bus_heat', 'heat_demand', 'flow')].plot(ax=ax1, linestyle='-', marker='o', color='r')

df[('thermal_storage', 'None', 'capacity')].plot.area(ax=ax2)

ax1.set_title('Heat flow to and from heat bus')
ax1.set_ylim(-2, 2)
ax1.legend(loc='center left', bbox_to_anchor=(1.0, 0.5))

ax2.set_title('Storage content')
ax2.set_xlabel('Timesteps')
ax2.legend(loc='center left', bbox_to_anchor=(1.0, 0.5))

plt.tight_layout()
plt.show()
