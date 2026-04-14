This module allows to compare two techmaps and highlight their differences.
It automatically reads the techmaps in directory v1 and v2 and compares them. The differences are highlighted in the output.
Make sure that only one techmap with the same name exists in both directories, otherwise the comparison will fail. 

Each techmap is an excel file which represents the input to cesm.
It has the following structure:
- Worksheet "Units":  quantity	scale_factor	input	output
- Worksheet "Scehnario": scenario_name	from_year	until_year	year_step	discount_rate	TSS	annual_co2_limit	co2_price
- Worksheet TSS: TSS_name	dt # TODO contains a bug currently, wrong dt for 4 thin weeks
- Worksheet "Commodity": commodity_name	order	color
- Worksheet "ConversionProces": conversion_process_name	order	color
- Worksheet "ConversionSubProces": conversion_process_name	commodity_in	commodity_out	scenario	spec_co2	efficiency	technical_lifetime	technical_availability	c_rate	efficiency_charge	is_storage	opex_cost_energy	opex_cost_power	capex_cost_power	capex_cost_base	cap_active	max_units	max_eout	min_eout	cap_min	cap_max	cap_res_min	cap_res_max	out_frac_min	out_frac_max	in_frac_min	in_frac_max	availability_profile	output_profile

The focus of the comparison is the worksheet ConversionSubProcess. Each row in the table represents a conversion subprocess. The comparison will highlight the differences in the parameters of the conversion subprocesses, such as efficiency, technical lifetime, technical availability, etc.

How to use:
1. Place the techmaps to be compared in the directories v1 and v2.
2. Run
```bash
uv run compare_techmaps
```