from typing import Dict,List,Tuple, Annotated, Any, Union
from collections import defaultdict
from pydantic import Field
from dataclasses import field
from pydantic.dataclasses import dataclass
from abc import ABC
import pickle

from pandas import DataFrame

OutputNonNegative = Annotated[float, Field(ge=-1e-5)]
NonNegative = Annotated[float, Field(ge=0)]
Positive = Annotated[float, Field(gt=0)]
PositiveInt = Annotated[int, Field(gt=0)]
Unit_in0_in1 = Annotated[float, Field(ge=0, le=1)]
Unit_ex0_in1 = Annotated[float, Field(gt=0, le=1)]


### Helper functions to avoid lambda functions, which can't be stored in a pickle file
def helper_zero():
    return 0
def one():
    return 1.0
def hundred():
    return 100    
###

def scale_dict(d: Dict[Any, float], scale: float) -> Dict[Any, float]:
    for k,v in d.items():
        d[k] = v*scale


@dataclass(frozen=True)
class IntData(ABC):
    _value: int
    def __int__(self):
        return self._value
    def __hash__(self) -> int:
        return hash(self._value)
    def __repr__(self) -> str:
        return str(self._value)
    
@dataclass(frozen=True)
class StrData(ABC):
    _value: str
    def __str__(self):
        return self._value
    def __hash__(self) -> int:
        return hash(self._value)
    def __repr__(self) -> str:
        return str(self._value)

@dataclass(frozen=True)
class Time(IntData):
    pass

@dataclass(frozen=True)
class Year(IntData):
    pass

@dataclass(frozen=True)
class ConversionProcess(StrData):
    pass
@dataclass(frozen=True)
class Commodity(StrData):
    pass

@dataclass(frozen=True)
class ConversionSubprocess:
    cp: ConversionProcess
    cin: Commodity
    cout: Commodity
    def __hash__(self) -> int:
        return hash((self.cp,self.cin,self.cout))
    def __repr__(self) -> str:
        return f"({repr(self.cp)},{repr(self.cin)},{repr(self.cout)})"

@dataclass
class Units:
    power: Positive
    energy: Positive
    co2_emissions: Positive
    cost_energy: Positive
    cost_power: Positive
    co2_spec: Positive

@dataclass
class Dataset:
    times: List[Time]
    years: List[Year]
    commodities: List[Commodity]
    conversion_processes: List[ConversionProcess]
    conversion_subprocesses: List[ConversionSubprocess]
    storage_cs: List[ConversionSubprocess]

    def __post_init__(self) -> None:
        self._validate_conversion_subprocesses()
    
    # -- Validator --
    def _validate_conversion_subprocesses(self) -> None:
        for cs in self.conversion_subprocesses:
            if cs.cp not in self.conversion_processes:
                raise ValueError(f"Conversion process {cs.cp} is not defined")
            if cs.cin not in self.commodities:
                raise ValueError(f"Commodity {cs.cin} is not defined")
            if cs.cout not in self.commodities:
                raise ValueError(f"Commodity {cs.cout} is not defined")

    def validate_y(self, years_set:List[Year]) -> None:
        for y in years_set:
            if y not in self.years:
                raise ValueError(f"Year {y} is not defined")
    
    def validate_t(self, time_set:List[Time]) -> None:
        for t in time_set:
            if t not in self.times:
                raise ValueError(f"Time {t} is not defined")
            
    def validate_cs(self, cs_set:List[ConversionSubprocess]) -> None:
        for cs in cs_set:
            if cs.cp not in self.conversion_processes:
                raise ValueError(f"Conversion process {cs.cp} is not defined")
            if cs.cin not in self.commodities:
                raise ValueError(f"Commodity {cs.cin} is not defined")
            if cs.cout not in self.commodities:
                raise ValueError(f"Commodity {cs.cout} is not defined")
        

@dataclass
class GlobalParam:
    dt: Positive
    discount_rate: Positive
    w: float = 1.0 
    discount_factor: Dict[Year,float] = field(init=False) # value is set in Input class

@dataclass      
class CostParam:
    opex_cost_energy: Dict[Tuple[ConversionSubprocess,Year], NonNegative]
    opex_cost_power: Dict[Tuple[ConversionSubprocess,Year], NonNegative]
    capex_cost_power: Dict[Tuple[ConversionSubprocess,Year], NonNegative]
    def __post_init__(self) -> None:
        self.opex_cost_energy = defaultdict(helper_zero, self.opex_cost_energy)
        self.opex_cost_power = defaultdict(helper_zero, self.opex_cost_power)
        self.capex_cost_power = defaultdict(helper_zero, self.capex_cost_power)
    
    def validate(self, dataset:Dataset) -> None:
        dataset.validate_cs([cs for (cs,y) in self.capex_cost_power.keys()])
        dataset.validate_y([y for (cs,y) in self.capex_cost_power.keys()])
        dataset.validate_cs([cs for (cs,y) in self.opex_cost_power.keys()])
        dataset.validate_y([y for (cs,y) in self.opex_cost_power.keys()])
        dataset.validate_cs([cs for (cs,y) in self.opex_cost_energy.keys()])
        dataset.validate_y([y for (cs,y) in self.opex_cost_energy.keys()])

    def scale(self, units: Units) -> None:
        scale_dict(self.opex_cost_energy, units.cost_energy)
        scale_dict(self.opex_cost_power, units.cost_power)
        scale_dict(self.capex_cost_power, units.cost_power)

@dataclass
class CO2Param:
    spec_co2: Dict[ConversionSubprocess, NonNegative]
    annual_co2_limit: Dict[Year, NonNegative]
    co2_price: Dict[Year, NonNegative]
    def __post_init__(self) -> None:
        self.spec_co2 = defaultdict(helper_zero, self.spec_co2)
        self.co2_price = defaultdict(helper_zero, self.co2_price)
    
    def validate(self, dataset:Dataset) -> None:
        dataset.validate_cs(self.spec_co2.keys())
        dataset.validate_y(self.co2_price.keys())
        dataset.validate_y(self.annual_co2_limit.keys())
    
    def scale(self, units: Units) -> None:
        scale_dict(self.spec_co2, units.co2_spec)

@dataclass
class EnergyParam:
    max_eout : Dict[Tuple[ConversionSubprocess,Year],NonNegative]
    min_eout : Dict[Tuple[ConversionSubprocess,Year],NonNegative]
    
    def validate(self, dataset:Dataset) -> None:
        dataset.validate_cs([cs for (cs,y) in self.max_eout.keys()])
        dataset.validate_y([y for (cs,y) in self.max_eout.keys()])
        dataset.validate_cs([cs for (cs,y) in self.min_eout.keys()])
        dataset.validate_y([y for (cs,y) in self.min_eout.keys()])

    def scale(self, units: Units) -> None:
        scale_dict(self.max_eout, units.energy)
        scale_dict(self.min_eout, units.energy)

@dataclass
class CapacityParam:
    cap_min: Dict[Tuple[ConversionSubprocess,Year],NonNegative]
    cap_max: Dict[Tuple[ConversionSubprocess,Year],NonNegative]
    cap_res_max: Dict[Tuple[ConversionSubprocess,Year],NonNegative]
    cap_res_min: Dict[Tuple[ConversionSubprocess,Year],NonNegative]
    def __post_init__(self) -> None:
        self.cap_res_max = defaultdict(helper_zero, self.cap_res_max)
    
    def validate(self, dataset:Dataset) -> None:
        dataset.validate_cs([cs for (cs,y) in self.cap_min.keys()])
        dataset.validate_y([y for (cs,y) in self.cap_min.keys()])
        dataset.validate_cs([cs for (cs,y) in self.cap_max.keys()])
        dataset.validate_y([y for (cs,y) in self.cap_max.keys()])
        dataset.validate_cs([cs for (cs,y) in self.cap_res_min.keys()])
        dataset.validate_y([y for (cs,y) in self.cap_res_min.keys()])
        dataset.validate_cs([cs for (cs,y) in self.cap_res_max.keys()])
        dataset.validate_y([y for (cs,y) in self.cap_res_max.keys()])

    def scale(self, units: Units) -> None:
        scale_dict(self.cap_min, units.power)
        scale_dict(self.cap_max, units.power)
        scale_dict(self.cap_res_min, units.power)
        scale_dict(self.cap_res_max, units.power)

@dataclass                                    
class TechnologyParam:
    efficiency: Dict[ConversionSubprocess, NonNegative]
    technical_lifetime: Dict[ConversionSubprocess, Positive]
    def __post_init__(self) -> None:
        self.efficiency = defaultdict(one, self.efficiency)
        self.technical_lifetime = defaultdict(hundred, {key:round(value) for key,value in self.technical_lifetime.items()})
    
    def validate(self, dataset:Dataset) -> None:
        dataset.validate_cs(self.efficiency.keys())
        dataset.validate_cs(self.technical_lifetime.keys())

@dataclass
class AvailabilityParam:
    availability_profile: Dict[Tuple[ConversionSubprocess,Time],Unit_in0_in1]
    technical_availability: Dict[ConversionSubprocess,Unit_in0_in1]
    output_profile: Dict[Tuple[ConversionSubprocess,Time], NonNegative]
    
    def __post_init__(self) -> None:
        self.technical_availability = defaultdict(one, self.technical_availability)
        self._validate_output_profile()
    def __repr__(self) -> str:
        return str(self.availability_profile) + str(self.technical_availability) + str(self.output_profile)
    
    def _validate_output_profile(self):
        for cs in {cs for (cs,t) in self.output_profile.keys()}:
            values = [value for key,value in self.output_profile.items() if key[0]==cs]
            if  len(values) > 0 and abs(sum(values) - 1.0) > 1e-4:
                raise ValueError("Demand profile must sum to 1.0")
        
    def validate(self, dataset:Dataset) -> None:
        dataset.validate_cs([cs for (cs,t) in self.availability_profile.keys()])
        dataset.validate_t([t for (cs,t) in self.availability_profile.keys()])
        dataset.validate_cs(self.technical_availability.keys())
        dataset.validate_cs([cs for (cs,t) in self.output_profile.keys()])
        dataset.validate_t([t for (cs,t) in self.output_profile.keys()])
        dataset.validate_y(self.discount_factor.keys())

@dataclass
class FractionParam:
    out_frac_min : Dict[Tuple[ConversionSubprocess,Year],Unit_in0_in1]
    out_frac_max : Dict[Tuple[ConversionSubprocess,Year],Unit_in0_in1]
    in_frac_min : Dict[Tuple[ConversionSubprocess,Year],Unit_in0_in1]
    in_frac_max : Dict[Tuple[ConversionSubprocess,Year],Unit_in0_in1]

    def validate(self, dataset:Dataset) -> None:
        dataset.validate_cs([cs for (cs,y) in self.out_frac_min.keys()])
        dataset.validate_y([y for (cs,y) in self.out_frac_min.keys()])
        dataset.validate_cs([cs for (cs,y) in self.out_frac_max.keys()])
        dataset.validate_y([y for (cs,y) in self.out_frac_max.keys()])
        dataset.validate_cs([cs for (cs,y) in self.in_frac_min.keys()])
        dataset.validate_y([y for (cs,y) in self.in_frac_min.keys()])
        dataset.validate_cs([cs for (cs,y) in self.in_frac_max.keys()])
        dataset.validate_y([y for (cs,y) in self.in_frac_max.keys()])

@dataclass
class StorageParam:
    c_rate: Dict[ConversionSubprocess, Positive]
    efficiency_charge: Dict[ConversionSubprocess, Unit_ex0_in1]
    def __post_init__(self) -> None:
        self.efficiency_charge = defaultdict(one, self.efficiency_charge)

    def validate(self, dataset:Dataset) -> None:
        dataset.validate_cs(self.c_rate.keys())
        dataset.validate_cs(self.efficiency_charge.keys())

@dataclass
class Param:
    globalparam: GlobalParam
    cost: CostParam
    co2: CO2Param
    energy: EnergyParam
    capacity: CapacityParam
    technology: TechnologyParam
    availability: AvailabilityParam
    fractions: FractionParam
    storage: StorageParam
    units: Units

    def __post_init__(self) -> None:
        self._scale()
    
    def validate(self, dataset:Dataset) -> None:
        self.cost.validate(dataset)
        self.co2.validate(dataset)
        self.energy.validate(dataset)
        self.capacity.validate(dataset)
        self.technology.validate(dataset)
        self.availability.validate(dataset)
        self.fractions.validate(dataset)
        self.storage.validate(dataset)
    
    def _scale(self) -> None:
        self.cost.scale(self.units)
        self.co2.scale(self.units)
        self.energy.scale(self.units)
        self.capacity.scale(self.units)

@dataclass
class PlotSettings:
    colors: Dict[str,str]
    orders: Dict[str,int]

@dataclass
class Input:
    param: Param
    dataset: Dataset
    plot_settings:PlotSettings
    def __post_init__(self) -> None:
        self.param.globalparam.discount_factor = {y:(1 + self.param.globalparam.discount_rate)**(int(self.dataset.years[0]) - int(y)) for y in self.dataset.years}
        # self.param.validate(self.dataset)


@dataclass
class CostOutput:
    OPEX: OutputNonNegative
    CAPEX: OutputNonNegative
    TOTEX: OutputNonNegative

@dataclass
class CO2Output:
    Total_annual_co2_emission: Dict[Year,OutputNonNegative]

@dataclass
class PowerOutput:
    Cap_new: Dict[Tuple[ConversionSubprocess,Year],OutputNonNegative]
    Cap_active: Dict[Tuple[ConversionSubprocess,Year],OutputNonNegative]
    Cap_res: Dict[Tuple[ConversionSubprocess,Year],OutputNonNegative]
    Pin: Dict[Tuple[ConversionSubprocess,Year,Time],OutputNonNegative]
    Pout: Dict[Tuple[ConversionSubprocess,Year,Time],OutputNonNegative]

@dataclass
class EnergyOutput:
    Eouttot: Dict[Tuple[ConversionSubprocess,Year],OutputNonNegative]
    Eintot: Dict[Tuple[ConversionSubprocess,Year],OutputNonNegative]
    Eouttime: Dict[Tuple[ConversionSubprocess,Year,Time],OutputNonNegative]
    Eintime: Dict[Tuple[ConversionSubprocess,Year,Time],OutputNonNegative]
    Enetgen: Dict[Tuple[Commodity,Year,Time],OutputNonNegative]
    Enetcons: Dict[Tuple[Commodity,Year,Time],OutputNonNegative]    

    
@dataclass
class StorageOutput:
    E_storage_level: Dict[Tuple[ConversionSubprocess,Year,Time],OutputNonNegative]
    E_storage_level_max: Dict[Tuple[ConversionSubprocess,Year],OutputNonNegative]


@dataclass
class Output:
    cost: CostOutput
    co2: CO2Output
    power: PowerOutput
    energy: EnergyOutput
    storage: StorageOutput


# -- Input and Output Saver and Reader --

# def save_input_output(input: Input, output:Output, filename: str):
#     """Save the input and output of the model in a .pkl file.

#     :param input: the input of the model
#     :type input: Input
#     :param output: the output of the model
#     :type output: Output
#     :param filename: the path of the file
#     :type filename: str
#     """
#     saved_dict = {"input": input, "output": output}
#     with open(filename, "wb") as f:
#         pickle.dump(saved_dict,f)

def read_input_output(filename:str):
    """
    Read the output of the model from a .pkl file.

    Args:
        filename: filename of saved output

    Return: 
        output: output from the Model as in the Output dataclass
    """
    with open(filename, "rb") as f:
        saved_dict = pickle.load(f)
        
    inp = saved_dict["input"]
    output = saved_dict["output"]
    return inp, output




# -- Helpers --

def _initialize_headers(key: Union[Time, Year, ConversionSubprocess,Commodity], current_headers: List[str]) -> List[str]:
    """gets the key of the dictionary and adds the corresponding headers to the current headers

    :param key: The key of the dictionary that is being converted to a DataFrame
    :type key: Time, Year, ConversionSubprocess, Commodity
    :param current_headers: list of current headers
    :type current_headers: List[str]
    :raises Exception: if the key type is not known
    :return: list of updated headers
    :rtype: List[str]
    """
    if isinstance(key, ConversionSubprocess):
        current_headers.extend(["cp", "cin", "cout"])
    elif isinstance(key, Commodity):
        current_headers.append("Commodity")
    elif isinstance(key, Year):
        current_headers.append("Year")
    elif isinstance(key, Time):
        current_headers.append("Time")
    else:
        raise Exception("Unknown key type")

    return current_headers

def _get_key_values(key: Union[Time, Year, ConversionSubprocess,Commodity], current_values: List[int|str]) -> List[int|str]:
    """gets the key or elements of the tuple key of the dictionary and adds the corresponding values to the current values

    :param key: The key of the dictionary that is being converted to a DataFrame
    :type key: Time, Year, ConversionSubprocess, Commodity
    :param current_values: list of current values
    :type current_values: List[int | str]
    :raises Exception: if the key type is not known
    :return: list of updated values
    :rtype: List[int|str]
    """
    if isinstance(key, ConversionSubprocess):
        current_values.extend([str(key.cp), str(key.cin), str(key.cout)])
    elif isinstance(key, Commodity):
        current_values.append(str(key))
    elif isinstance(key, Year):
        current_values.append(int(key))
    elif isinstance(key, Time):
        current_values.append(int(key))
    else:
        raise Exception("Unknown key type")

    return current_values

def get_as_dataframe(obj: Dict[Any,float], **filterby) -> DataFrame:
    """gets a dictionary of the input or output data classes and converts it to a pandas DataFrame

    :param obj: a dictionary of the input or output data classes
    :type obj: Dict[Any,float]
    :raises Exception: if the key type is not known
    :return: a pandas DataFrame
    :rtype: DataFrame
    """
    headers, ret = [], []

    # Get keys and values
    keys = list(obj.keys())
    
    # Initialize headers
    if isinstance(keys[0], tuple):
        for kp in keys[0]:
            headers = _initialize_headers(kp, headers)
    else:
        headers = _initialize_headers(keys[0], headers)
                    
    headers.append('value')

    # Initialize rows
    for key, val in obj.items():
        row = []
        if isinstance(key, tuple):
            for kp in key:
                row = _get_key_values(kp, row)
        else:
            row = _get_key_values(key, row)
        row.append(val)
        ret.append(tuple(row))
    
    # Build and Filter
    df = DataFrame(ret, columns=headers)
    for k, v in filterby.items():
        try:
            df = df[df[k] == v]
        except KeyError:
            raise Exception(f"Key {k} not found in DataFrame! Existing keys: {df.columns}")

    return df