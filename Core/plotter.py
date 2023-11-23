# --------------------------------------------------
#  Plotter class with Plotly
#  Julia Barbosa
#  mail@juliabarbosa.net
# -------------------------------------------------- 

import plotly.graph_objects as go
import plotly.colors as plc

from Core.datacls import Input, Output, get_as_dataframe, read_input_output

import pandas as pd
import random
from enum import Enum, member
from typing import List

class PlotterExeption(Exception):
   pass



# -- Enums --
class Bar(Enum):
   ENERGY_CONSUMPTION = 1
   ENERGY_PRODUCTION = 2
   ACTIVE_CAPACITY = 3
   NEW_CAPACITY = 4 
   CO2_EMISSION = 5
   PRIMARY_ENERGY = 6
   CO2_PRICE = 7

class SingleValue(Enum):

   CAPEX = 8
   OPEX = 9
   TOTEX = 10

class TimeSeries(Enum):
   ENERGY_CONSUMPTION = 1
   ENERGY_PRODUCTION = 2
   POWER_CONSUMPTION = 3
   POWER_PRODUCTION = 4

class Sankey(Enum):
   SANKEY = 1

class PlotType:
   Bar = Bar
   TimeSeries = TimeSeries
   Sankey = Sankey
   SingleValue = SingleValue

 
 
# -- Helper Private Functions --

def _rand_hex_color():
   return "#{:06x}".format(random.randint(0, 0xFFFFFF))

def _hex_to_rgba(hexarray, alpha):
    ret = []
    for col in hexarray:
        color_tuple = plc.hex_to_rgb(col)
        ret.append("rgba(%s, %s, %s, %s)" %(*color_tuple, alpha))
    return ret


# -- Plotter Class --
class Plotter:
    
   def __init__(self, ipt:Input, otp:Output):
      self.input = ipt
      self.output = otp

      self.plot_setings = dict(
         font_family="Knuth's Computer Modern",
         template="plotly_white",
         showlegend=True,
         barmode="stack",
         sankey_link_opacity=0.5,
      )

      self._colors = ipt.plot_settings.colors
      self._order =  ipt.plot_settings.orders


   # -- Main Plotting Functions --   
   def plot_sankey(self, year:int):
      """Plots a Sankey Diagram for the given year
      Args:
          year (int): Year to plot

      """
      
      self._check_year(year)
      
      # Energy Use: Cin -> CP
      consumption = get_as_dataframe(self.output.energy.Eintot, Year=year)
      consumption.rename(columns={"cp":"target", "cin":"source"}, inplace=True)
      
      # Energy Production: -> CP -> Cout
      production = get_as_dataframe(self.output.energy.Eouttot, Year=year)
      production.rename(columns={"cp":"source", "cout":"target"}, inplace=True)

      # Join Dataframes and remove Dummy Nodes
      sankey_df = pd.concat([consumption.loc[:,["source","target", "value"]],
                             production.loc[:,["source","target", "value"]]])
      sankey_df = sankey_df.loc[sankey_df["source"] != "Dummy"]
      sankey_df = sankey_df.loc[sankey_df["target"] != "Dummy"]

      # Main Sankey Plot
      nodes = list(sankey_df["source"]) + list(sankey_df["target"])
      nodes = list(set(nodes))
      id_fun = lambda x: nodes.index(x)
      sankey_df["source_i"] = sankey_df["source"].apply(id_fun)
      sankey_df["target_i"] = sankey_df["target"].apply(id_fun)


      
      fig = go.Figure(data=[go.Sankey(
            arrangement='perpendicular',
            node=dict(
                # pad=30,
                thickness=10,
                line=dict(color="black", width=0.01),
                label=nodes,
                color=_hex_to_rgba([self._get_color(n) for n in nodes], 0.8)
            ),
            link=dict(
                source=sankey_df["source_i"],
                target=sankey_df["target_i"],
                value=sankey_df["value"],
    
            ))])

      fig.update_layout(title_text="%s Sankey"%year, font_size=12)
      # fig.show()
      return fig

   def plot_single_value(self, single_value_type: list[PlotType.SingleValue]):
      # Gather Data
      data = dict()
      for sv_ty in single_value_type:
         if sv_ty == PlotType.SingleValue.CAPEX:
            data["CAPEX"] = self.output.cost.CAPEX
         elif sv_ty == PlotType.SingleValue.OPEX:
            data["OPEX"] = self.output.cost.OPEX
         elif sv_ty == PlotType.SingleValue.TOTEX:
            data["TOTEX"] = self.output.cost.TOTEX
         else:
            raise PlotterExeption("Invalid type for plotting!")
      
      # Create Figure
      traces = go.Bar(x=list(data.keys()), y=list(data.values()))
      layout = self._get_default_layout(title="Costs", yaxistitle="Costs [€]")
      fig = go.Figure(data=traces, layout=layout)
      fig.show()





   def plot_bars(self, bar_type: PlotType.Bar, commodity=None):
      """Main function for plotting bar plots

      Args:
          bar_type (BarPlotType): Type of bar plot to plot
          commodity (str, optional): Commodity to Plot. It has to be defined to some plot types. Defaults to None.

      Raises:
          PlotterExeption: Asked for a plot that requires a commodity but none was given!
          PlotterExeption: Invalid type for plotting!
      """

      stacks = 'cp' # Default Stacks

      if bar_type == PlotType.Bar.CO2_EMISSION:
         data = get_as_dataframe(self.output.co2.Total_annual_co2_emission)
         title = f"CO2 Emission for {commodity}"
         stacks = None
         yaxis = "CO2 [t]"

      elif bar_type == PlotType.Bar.CO2_PRICE:
         data = get_as_dataframe(self.input.param.co2.co2_price)
         title = f"CO2 Price"
         stacks = None
         yaxis = "Price [€/t]"


      elif bar_type == PlotType.Bar.PRIMARY_ENERGY:
         data = get_as_dataframe(self.output.energy.Eouttot, cin="Dummy")
         title = f"Primary Energy Use"
         yaxis = "Energy [MWh]"
      
      else:
         # Check if commodity is set
         self._check_commodity(commodity)
         if commodity is None:
            raise PlotterExeption("Commodity must be set for this plot!")
         
         elif bar_type == PlotType.Bar.ENERGY_CONSUMPTION:
            data = get_as_dataframe(self.output.energy.Eintot, cin=commodity)
            title = f"Energy Consumption for {commodity}"
            yaxis = "Energy [MWh]"
         elif bar_type == PlotType.Bar.ENERGY_PRODUCTION:
            data = get_as_dataframe(self.output.energy.Eouttot, cout=commodity)
            title = f"Energy Production for {commodity}"
            yaxis = "Energy [MWh]"
         elif bar_type == PlotType.Bar.ACTIVE_CAPACITY:
            data = get_as_dataframe(self.output.power.Cap_active, cout=commodity)
            title = f"Active Capacity for {commodity}"
            yaxis = "Power [MW]"
         elif bar_type == PlotType.Bar.NEW_CAPACITY:
            data = get_as_dataframe(self.output.power.Cap_new, cout=commodity)
            title = f"New Capacity for {commodity}"
            yaxis = "Power [MW]"
         else:
            raise PlotterExeption("Invalid type for plotting!")


      # Create Figure
      trace = self._get_traces(data, type="bar", stacks=stacks)
      layout = self._get_default_layout(title=title, yaxistitle=yaxis)
      fig = go.Figure(data=trace, layout=layout)

      fig.show()

   def plot_timeseries(self, timeseries_type: PlotType.TimeSeries, year:int, commodity:str):
      """Main function for plotting timeseries

      Args:
          timeseries_type (TimeSeriesType): Timeseries type to plot
          year (int): year to plot
          commodity (str): Commodity to plot

      Raises:
          PlotterExeption: Invalid type for plotting!
      """

      stacks = "cp" # Default Stacks

      if timeseries_type == PlotType.TimeSeries.ENERGY_CONSUMPTION:
         data = get_as_dataframe(self.output.energy.Eintime, cin=commodity, Year=year)
         title = f"Energy Consumption for {commodity} in {year}"
         yaxis = "Energy [MWh]"
      
      elif timeseries_type == PlotType.TimeSeries.ENERGY_PRODUCTION:
         data = get_as_dataframe(self.output.energy.Eouttime, cout=commodity, Year=year)
         title = f"Energy Production for {commodity} in {year}"
         yaxis = "Energy [MWh]"
     
      elif timeseries_type == PlotType.TimeSeries.POWER_CONSUMPTION:
         data = get_as_dataframe(self.output.power.Pin, cin=commodity, Year=year)
         title = f"Power Consumption for {commodity} in {year}"
         yaxis = "Power [MW]"
      
      elif timeseries_type == PlotType.TimeSeries.POWER_PRODUCTION:
         data = get_as_dataframe(self.output.power.Pout, cout=commodity, Year=year)
         title = f"Power Production for {commodity} in {year}"
         yaxis = "Power [MW]"

      else:
         raise PlotterExeption("Invalid type for plotting!")
      
      # Create Figure
      trace = self._get_traces(data, type="timeseries", x="Time", stacks=stacks)
      layout = self._get_default_layout(title=title, yaxistitle=yaxis, xaxistitle="Time")
      fig = go.Figure(data=trace, layout=layout)
      fig.show()


   def _get_traces(self, df, type, x="Year", y="value", stacks="cp") -> List[go.Bar]:
      """Returns a list of traces for plotting

      Args:
          df (DataFrame): Dataframe with data to plot
          type (str): Type of plot, bar or timeseries
          x (str, optional): Values to be plotted on X axis, must be a column of df. Defaults to "Year".
          y (str, optional): Colunm name for Y axis data. Defaults to "value".
          stacks (str, optional): Colunm name of group to be used as stacks. If Let None it will have a single stack. Defaults to "cp".

      Raises:
          PlotterExeption: Empty Dataframe
          PlotterExeption: Invalid type for plotting!

      Returns:
          List[go.Bar]: List of traces for plotting
      """

      # TODO: Correct Time Series Plotting -> get rid of empty timesteps

      if df.size == 0:
         raise PlotterExeption("No results to plot!")

      traces = []

      # Sort Stacks
      if stacks is not None:
         df.loc[:, "stacks_sorting"] = df[stacks].apply(lambda x: self._get_order(x))
         df = df.sort_values(by=["stacks_sorting"], ascending=[True])
      else:
         stacks = "Unique"
         df[stacks] = stacks
         
     
      for st, in zip(df[stacks].unique()):
         plot_df = df[df[stacks] == st]
         if type == "bar":
               t = go.Bar(x=plot_df[x], y=plot_df[y],  name=st, marker_color=self._get_color(st))
         elif type == "timeseries":
               t = go.Scatter(x=plot_df[x], y=plot_df[y], name=st, stackgroup="one",
                              mode="none", fillcolor=self._get_color(st))
         else:
               raise PlotterExeption("Invalid type for plotting!")
         traces.append(t)
      return traces


   # -- Validators --
   def _check_year(self, year:int):
      if year not in [int(y) for y in self.input.dataset.years]:
         raise PlotterExeption(f"Year {year} not in model!")

   def _check_commodity(self, commodity:str):
      if commodity not in [str(co) for co in self.input.dataset.commodities]:
         raise PlotterExeption(f"Commodity {commodity} not in model!")


   # -- Configuration Selectors --
   def _get_default_layout(self, title=None, yaxistitle=None, xaxistitle="Year"):
      return go.Layout(
         showlegend=self.plot_setings["showlegend"],
         font_family=self.plot_setings["font_family"],
         template="plotly_white",
         title=title,
         xaxis=dict(title_text=xaxistitle),
         yaxis=dict(title_text=yaxistitle),
         barmode=self.plot_setings["barmode"],
      )
   
   def _get_color(self, name:str):
      if name not in self._colors:
         self._colors[name] = _rand_hex_color()
      return self._colors[name]

   def _get_order(self, name:str):
      if name not in self._order:
         self._order[name] = random.randint(0,100)
      return self._order[name]

   @property
   def link_opacity(self):
      return self.plot_setings["sankey_link_opacity"]


# -- Fast Tests - Examples--
if __name__ == "__main__":
   pass


