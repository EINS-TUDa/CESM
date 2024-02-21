CLI(Command Line Interface)
============================
You can use run and visualize the results with CLI, without writting any piece of code. The results of each simulation are stored in the ``Runs`` directory. To run the model with  CLI you have to use the following command:
.. code-block:: console

   > python cesm.py run

then it asks for the model that you want to run and the name of the scenario. 

To visualize the results of a simulation you have to use the following command:

.. code-block:: console

   > python cesm.py plot

Then it asks for the name of the model and the scenario, the type of the plot and the variable to plot.
