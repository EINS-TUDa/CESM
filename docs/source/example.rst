Examples
========

In this section, we show how to model some of the common energy systems technologies using the abstraction proposed in the model.

.. _CHP:

Combined Heat and Power Plant(CHP)
----------------------------------

CHPs can be modeled by combining 4 conversion subprocesses and an auxiliary commodity.
All conversion subprocesses are assumed to have efficiency 1.
Using the parameters minimum/maximum fraction of input commodity consumption, one can define the maximum efficiency and ranges for the output of heat and electricity. 

.. image:: ./figures/CHP.svg

.. _decentralized_heating:

Decentral Heating
-----------------

For large energy systems, such as the German model, it is not practical to model every heating system individually, especially for decentral heating where the number of heating systems is very large.
In this case, the heating systems of a kind are aggregated under a single conversion process. 
However, for household heating, it is not reasonable to assume that different types of heating systems, e.g. gas and heat pumps, are able to complement each other, as each house has only one heating system.
Therefore, in this case, the output profile of heating technologies that provide decentral heating is constrained to have the same load profile as the demand for decentral heating.

.. image:: ./figures/decentral_heat.svg

Renewables
----------

Renewables are modeled as conversion processes with efficiency 1 and a maximum capacity. 
They are assumed to have no marginal cost and no emissions and convert "Dummy" into, for example, "Electricity". 
The user provides an additional availability profile, which is composed of a time series with values between 0 and 1.
The availability profile is used to constrain the output of the conversion process to be smaller than the maximum capacity multiplied by the availability profile.

.. image:: ./figures/renewable.svg





