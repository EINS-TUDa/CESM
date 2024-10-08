Techmap
============================

Tabs
--------------

* Units
    * power: :math:`cap\_min`, :math:`cap\_max`, :math:`cap\_res\_max`, :math:`cap\_res\_min`
    * energy: :math:`max\_eout`, :math:`min\_eout`
    * co2_emission: not_implemented
    * cost_energy: :math:`opex\_cost\_energy`
    * cost_power: :math:`opex\_cost\_power`, :math:`capex\_cost\_power`
    * co2_spec: :math:`spec\_co2`
    * money: not_implemented 
* Scenario
    * discount_rate: Discount rate
    * annual_co2_limit: It is an annual parameter and is in the form explained in the :ref:`annual-value` section.
    * co2_price: the default value is 0.
    * from_year: the modeling time starts from this year.
    * until_year: the modeling time ends at this year.
    * year_step: the step size of the time series.
    * TSS: Time-Series Selection. The name should match one of the items in the TSS tab.
* Commodity
    * commodity: the name of the commodity.
    * description: the description of the commodity. It is used for the documentation.
* ConversionProcess
    * conversion_process_name: the name of the conversion process.
    * description: the description of the commodity. It is used for the documentation.
* ConversionSubProcess
    * ...
* TSS
    * TSS_name: the name of the time series selection.
    * description: the description of the time series selection. It is used for the documentation.
    * dt: the time step of the simulation.
    TSS files contains the index of time steps which are considered in the formulation. The index starts from 1. For example if it contains 1,2,3,11,12,13 then six time steps are considered in the formulation.
    It also tells that the 1st, 2nd, 3rd, 11th, 12th, 13th elements of the time dependent input data, that is provided in a text file, are considered in the formulation.


Time Dependent Parameters
-------------------------

Reads the corresponding items from the specified data files. The items which are referenced in the times series selection are only considered in the simulation.

.. _annual-value:

Annual Parameters
-------------------------

* single value: The value is the same for all the years.
* linear interpolation
    * [2015 5; 2020 6;2030 7;2050 10]: 5 in 2015 and the previous years and 10 in 2050 and the next years. The value for the years between 2015 and 2050 is linearly interpolated.
    * [2015 0;2016 NaN]: It means 0 in 2015 and the previous years and the value is not specified for the next years.

year dependent parameters
interpolation