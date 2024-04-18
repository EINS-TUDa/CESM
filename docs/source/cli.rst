CLI(Command Line Interface)
============================

This command structures the directories and initial files necessary for the software to run.

.. code-block:: console

   > cesm init

You can run and visualize the results using the CLI without writing any code. The results of each simulation are stored in the ``Runs`` directory. To run the model with CLI, use the following command:
.. code-block:: console

   > cesm run

The CLI will prompt for the model you want to run and the name of the scenario.

To visualize the results of a simulation, use the following command:

.. code-block:: console

   > python cesm.py plot

You'll be prompted for the model name, scenario, plot type, and variable to plot.
