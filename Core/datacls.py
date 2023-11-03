from typing import Dict,List,Tuple,Set, Annotated, Any
from collections import defaultdict
from pydantic import Field
from dataclasses import field
from pydantic.dataclasses import dataclass

NonNegative = Annotated[float, Field(ge=0)]
Positive = Annotated[float, Field(gt=0)]
PositiveInt = Annotated[int, Field(gt=0)]
Unit_in0_in1 = Annotated[float, Field(ge=0, le=1)]
Unit_ex0_in1 = Annotated[float, Field(gt=0, le=1)]

def scale_dict(d: Dict[Any, float], scale: float) -> Dict[Any, float]:
    for k,v in d.items():
        d[k] = v*scale

@dataclass(frozen=True)
class Time:
    _value: int
    def __int__(self):
        return self._value
    def __hash__(self) -> int:
        return hash(self._value)
    def __repr__(self) -> str:
        return str(self._value)

@dataclass(frozen=True)
class Year:
    _value: int
    def __int__(self):
        return self._value
    def __hash__(self) -> int:
        return hash(self._value)
    def __repr__(self) -> str:
        return str(self._value)

@dataclass(frozen=True)
class ConversionProcess:
    _value: str
    def __str__(self):
        return self._value
    def __hash__(self) -> int:
        return hash(self._value)
    def __repr__(self) -> str:
        return str(self._value)

@dataclass(frozen=True)
class Commodity:
    _value: str
    def __str__(self):
        return self._value
    def __hash__(self) -> int:
        return hash(self._value)
    def __repr__(self) -> str:
        return str(self._value)

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
    commodities: Set[Commodity]
    conversion_processes: Set[ConversionProcess]
    conversion_subprocesses: Set[ConversionSubprocess]
    storage_cs: Set[ConversionSubprocess]

    def __post_init__(self) -> None:
        self._validate_conversion_subprocesses()
    
    def _validate_conversion_subprocesses(self) -> None:
        for cs in self.conversion_subprocesses:
            if cs.cp not in self.conversion_processes:
                raise ValueError(f"Conversion process {cs.cp} is not defined")
            if cs.cin not in self.commodities:
                raise ValueError(f"Commodity {cs.cin} is not defined")
            if cs.cout not in self.commodities:
                raise ValueError(f"Commodity {cs.cout} is not defined")

    def validate_y(self, years_set:Set[Year]) -> None:
        for y in years_set:
            if y not in self.years:
                raise ValueError(f"Year {y} is not defined")
    
    def validate_t(self, time_set:Set[Time]) -> None:
        for t in time_set:
            if t not in self.times:
                raise ValueError(f"Time {t} is not defined")
            
    def validate_cs(self, cs_set:Set[ConversionSubprocess]) -> None:
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

@dataclass      
class CostParam:
    opex_cost_energy: Dict[Tuple[ConversionSubprocess,Year], NonNegative] = field(default_factory=dict)
    opex_cost_power: Dict[Tuple[ConversionSubprocess,Year], NonNegative] = field(default_factory=dict)
    capex_cost_power: Dict[Tuple[ConversionSubprocess,Year], NonNegative] = field(default_factory=dict)
    def __post_init__(self) -> None:
        self.opex_cost_energy = defaultdict(lambda: 0, self.opex_cost_energy)
        self.opex_cost_power = defaultdict(lambda: 0, self.opex_cost_power)
        self.capex_cost_power = defaultdict(lambda: 0, self.capex_cost_power)
    
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
    spec_co2: Dict[ConversionSubprocess, NonNegative] = field(default_factory=dict)
    annual_co2_limit: Dict[Year, NonNegative] = field(default_factory=dict)
    co2_price: Dict[Year, NonNegative] = field(default_factory=dict)
    def __post_init__(self) -> None:
        self.spec_co2 = defaultdict(lambda: 0, self.spec_co2)
        self.co2_price = defaultdict(lambda: 0, self.co2_price)
    
    def validate(self, dataset:Dataset) -> None:
        dataset.validate_cs(self.spec_co2.keys())
        dataset.validate_y(self.co2_price.keys())
        dataset.validate_y(self.annual_co2_limit.keys())
    
    def scale(self, units: Units) -> None:
        scale_dict(self.spec_co2, units.co2_spec)

@dataclass
class EnergyParam:
    max_eout : Dict[Tuple[ConversionSubprocess,Year],NonNegative] = field(default_factory=dict)
    min_eout : Dict[Tuple[ConversionSubprocess,Year],NonNegative] = field(default_factory=dict)
    
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
    cap_min: Dict[Tuple[ConversionSubprocess,Year],NonNegative] = field(default_factory=dict)
    cap_max: Dict[Tuple[ConversionSubprocess,Year],NonNegative] = field(default_factory=dict)
    cap_res_max: Dict[Tuple[ConversionSubprocess,Year],NonNegative] = field(default_factory=dict)
    cap_res_min: Dict[Tuple[ConversionSubprocess,Year],NonNegative] = field(default_factory=dict)
    def __post_init__(self) -> None:
        self.cap_res_max = defaultdict(lambda: 0, self.cap_res_max)
    
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
    efficiency: Dict[ConversionSubprocess, NonNegative] = field(default_factory=dict)
    technical_lifetime: Dict[ConversionSubprocess, Positive] = field(default_factory=dict)
    def __post_init__(self) -> None:
        self.efficiency = defaultdict(lambda: 1.0, self.efficiency)
        self.technical_lifetime = defaultdict(lambda: 100, {key:round(value) for key,value in self.technical_lifetime.items()})
    
    def validate(self, dataset:Dataset) -> None:
        dataset.validate_cs(self.efficiency.keys())
        dataset.validate_cs(self.technical_lifetime.keys())

@dataclass
class AvailabilityParam:
    availability_factor: Dict[Tuple[ConversionSubprocess,Time],Unit_in0_in1] = field(default_factory=dict)
    technical_availability: Dict[ConversionSubprocess,Unit_in0_in1] = field(default_factory=dict)
    demand_factor: Dict[Tuple[ConversionSubprocess,Time], NonNegative] = field(default_factory=dict)
    discount_factor: Dict[Year,float] = field(init=False) # value is set in Input class
    def __post_init__(self) -> None:
        self.technical_availability = defaultdict(lambda: 1.0, self.technical_availability)
        self._validate_demand_factor()
    def __repr__(self) -> str:
        return str(self.availability_factor) + str(self.technical_availability) + str(self.demand_factor)
    
    def _validate_demand_factor(self):
        for cs in {cs for (cs,t) in self.demand_factor.keys()}:
            values = [value for key,value in self.demand_factor.items() if key[0]==cs]
            if  len(values) > 0 and abs(sum(values) - 1.0) > 1e-4:
                raise ValueError("Demand factors must sum to 1.0")
        
    def validate(self, dataset:Dataset) -> None:
        dataset.validate_cs([cs for (cs,t) in self.availability_factor.keys()])
        dataset.validate_t([t for (cs,t) in self.availability_factor.keys()])
        dataset.validate_cs(self.technical_availability.keys())
        dataset.validate_cs([cs for (cs,t) in self.demand_factor.keys()])
        dataset.validate_t([t for (cs,t) in self.demand_factor.keys()])
        dataset.validate_y(self.discount_factor.keys())


@dataclass
class FractionParam:
    out_frac_min : Dict[Tuple[ConversionSubprocess,Year],Unit_in0_in1] = field(default_factory=dict)
    out_frac_max : Dict[Tuple[ConversionSubprocess,Year],Unit_in0_in1] = field(default_factory=dict)
    in_frac_min : Dict[Tuple[ConversionSubprocess,Year],Unit_in0_in1] = field(default_factory=dict)
    in_frac_max : Dict[Tuple[ConversionSubprocess,Year],Unit_in0_in1] = field(default_factory=dict)

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
    c_rate: Dict[ConversionSubprocess, Positive] = field(default_factory=dict)
    efficiency_charge: Dict[ConversionSubprocess, Unit_ex0_in1] = field(default_factory=dict)
    def __post_init__(self) -> None:
        self.efficiency_charge = defaultdict(lambda: 1.0, self.efficiency_charge)

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
class Input:
    param: Param
    dataset: Dataset

    def __post_init__(self) -> None:
        self.param.availability.discount_factor = {y:(1 + self.param.globalparam.discount_rate)**(int(self.dataset.years[0]) - int(y)) for y in self.dataset.years}
        # self.param.validate(self.dataset)



@dataclass
class CostOutput:
    OPEX: Positive
    CAPEX: Positive
    TOTEX: Positive

@dataclass
class CO2Output:
    Total_annual_co2_emission: Positive

@dataclass
class PowerOutput:
    Cap_new: Dict[Tuple[ConversionSubprocess,Year],Positive]
    Cap_active: Dict[Tuple[ConversionSubprocess,Year],Positive]
    Cap_res: Dict[Tuple[ConversionSubprocess,Year],Positive]
    Pin: Dict[Tuple[ConversionSubprocess,Year],Positive]
    Pout: Dict[Tuple[ConversionSubprocess,Year],Positive]

@dataclass
class EnergyOutput:
    Eouttot: Dict[Tuple[ConversionSubprocess,Year],Positive]
    Eintot: Dict[Tuple[ConversionSubprocess,Year],Positive]
    Eouttime: Dict[Tuple[ConversionSubprocess,Year,Time],Positive]
    Eintime: Dict[Tuple[ConversionSubprocess,Year,Time],Positive]
    Enetgen: Dict[Tuple[Commodity,Year,Time],Positive]
    Enetcons: Dict[Tuple[Commodity,Year,Time],Positive]

@dataclass
class StorageOutput:
    E_storage_level: Dict[Tuple[ConversionSubprocess,Year,Time],Positive]
    E_storage_level_max: Dict[Tuple[ConversionSubprocess,Year],Positive]


@dataclass
class Output:
    cost: CostOutput
    co2: CO2Output
    power: PowerOutput
    energy: EnergyOutput
    storage: StorageOutput