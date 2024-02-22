from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from Core import datacls as dtcls
from sqlalchemy.orm import Session

from sqlalchemy import create_engine
engine = create_engine("sqlite://", echo=True)

class Base(DeclarativeBase):
    pass

class Time(Base):
    __tablename__ = "time"
    id: Mapped[int] = mapped_column(primary_key=True)
    order: Mapped[int] = mapped_column(nullable=False)
    value: Mapped[int] = mapped_column(nullable=False)

class Year(Base):
    __tablename__ = "year"
    id: Mapped[int] = mapped_column(primary_key=True)
    order: Mapped[int] = mapped_column(nullable=False)
    value: Mapped[int] = mapped_column(nullable=False)

class Commodity(Base):
    __tablename__ = "commodity"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))

class ConversionProcess(Base):
    __tablename__ = "conversion_process"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))

class ConversionSubprocess(Base):
    __tablename__ = "conversion_subprocess"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    cin_id: Mapped[int] = mapped_column(ForeignKey("commodity.id"))
    cin: Mapped["Commodity"] = relationship(back_populates="conversion_subprocesses_in")
    cout_id: Mapped[int] = mapped_column(ForeignKey("commodity.id"))
    cout: Mapped["Commodity"] = relationship(back_populates="conversion_subprocesses_out")
    cp_id: Mapped[int] = mapped_column(ForeignKey("conversion_process.id"))
    cp: Mapped["ConversionProcess"] = relationship(back_populates="conversion_process")

class Param(Base):
    __tablename__ = "param"
    id: Mapped[int] = mapped_column(primary_key=True)
    dt: Mapped[float] = mapped_column(nullable=False)
    discount_rate: Mapped[float] = mapped_column(nullable=False)

class Param_CS(Base):
    __tablename__ = "param_cs"
    id: Mapped[int] = mapped_column(primary_key=True)
    spec_co2: Mapped[float] = mapped_column(nullable=True)
    efficiency: Mapped[float] = mapped_column(nullable=True)
    technology_lifetime: Mapped[float] = mapped_column(nullable=True)
    technical_availability: Mapped[float] = mapped_column(nullable=True)
    c_rate: Mapped[float] = mapped_column(nullable=True)
    efficiency_charge: Mapped[float] = mapped_column(nullable=True)
    cs: Mapped["ConversionSubprocess"] = relationship()

class Param_Y(Base):
    __tablename__ = "param_y"
    id: Mapped[int] = mapped_column(primary_key=True)
    annual_co2_limit: Mapped[float] = mapped_column(nullable=True)
    co2_price: Mapped[float] = mapped_column(nullable=True)
    y: Mapped["Year"] = relationship()

class Param_CS_Y(Base):
    __tablename__ = "param_cs_y"
    id: Mapped[int] = mapped_column(primary_key=True)
    opex_cost_energy: Mapped[float] = mapped_column(nullable=True)
    opex_cost_power: Mapped[float] = mapped_column(nullable=True)
    capex_cost_power: Mapped[float] = mapped_column(nullable=True)
    max_eout: Mapped[float] = mapped_column(nullable=True)
    min_eout: Mapped[float] = mapped_column(nullable=True)
    cap_min: Mapped[float] = mapped_column(nullable=True)
    cap_max: Mapped[float] = mapped_column(nullable=True)
    cap_res_max: Mapped[float] = mapped_column(nullable=True)
    cap_res_min: Mapped[float] = mapped_column(nullable=True)
    out_frac_min: Mapped[float] = mapped_column(nullable=True)
    out_frac_max: Mapped[float] = mapped_column(nullable=True)
    in_frac_min: Mapped[float] = mapped_column(nullable=True)
    in_frac_max: Mapped[float] = mapped_column(nullable=True)
    cs: Mapped["ConversionSubprocess"] = relationship()
    y: Mapped["Year"] = relationship()

class Param_CS_T(Base):
    __tablename__ = "param_cs_t"
    id: Mapped[int] = mapped_column(primary_key=True)
    availability_profile: Mapped[float] = mapped_column(nullable=True)
    output_profile: Mapped[float] = mapped_column(nullable=True)
    cs: Mapped["ConversionSubprocess"] = relationship()
    t: Mapped["Time"] = relationship()


def generate_db_input(input: dtcls.Input) -> None:
    times = {}
    for i, t in enumerate(input.dataset.times):
        times[t] = Time(order=i, value=int(t))
    years = {}
    for i, y in enumerate(input.dataset.years):
        years[y] = Year(order=i, value=int(y))
    commodities = {}
    for co in input.dataset.commodities:
        commodities[co] = Commodity(name=str(co))
    conversion_processes = {}
    for cp in input.dataset.conversion_processes:
        conversion_processes[cp] = ConversionProcess(name=str(cp))
    conversion_subprocesses = {}
    for cs in input.dataset.conversion_subprocesses:
        conversion_subprocesses[cs] = ConversionSubprocess(name=str(cs), cin=commodities[cs.cin], cout=commodities[cs.cout], cp=conversion_processes[cs.cp]) 

    param_global = Param(dt=input.param.globalparam.dt, discount_rate=input.param.globalparam.discount_rate)
    param_cs = {}
    for cs in conversion_processes:
        temp = {}
        temp["spec_co2"] = input.param.co2.spec_co2.get(cs, None)
        temp["efficiency"] = input.param.technology.efficiency.get(cs, None)
        temp["technology_lifetime"] = input.param.technology.technology_lifetime.get(cs, None)
        temp["technical_availability"] = input.param.availability.technical_availability.get(cs, None)
        temp["c_rate"] = input.param.storage.c_rate.get(cs, None)
        temp["efficiency_charge"] = input.param.storage.efficiency_charge.get(cs, None)
        if any([val is not None for val in temp.values()]):
            param_cs[cs] = Param_CS(**temp, cs=conversion_subprocesses[cs])
        
    param_y = {}
    for y in years:
        temp = {}
        temp["annual_co2_limit"] = input.param.co2.annual_co2_limit.get(y, None)
        temp["co2_price"] = input.param.co2.co2_price.get(y, None)
        if any([val is not None for val in temp.values()]):
            param_y[y] = Param_Y(**temp, y=years[y])
    
    param_cs_y = {}
    for cs in conversion_subprocesses:
        for y in years:
            temp = {}
            temp["opex_cost_energy"] = input.param.cost.opex_cost_energy.get((cs, y), None)
            temp["opex_cost_power"] = input.param.cost.opex_cost_power.get((cs, y), None)
            temp["capex_cost_power"] = input.param.cost.capex_cost_power.get((cs, y), None)
            temp["max_eout"] = input.param.energy.max_eout.get((cs, y), None)
            temp["min_eout"] = input.param.energy.min_eout.get((cs, y), None)
            temp["cap_min"] = input.param.capacity.cap_min.get((cs, y), None)
            temp["cap_max"] = input.param.capacity.cap_max.get((cs, y), None)
            temp["cap_res_max"] = input.param.capacity.cap_res_max.get((cs, y), None)
            temp["cap_res_min"] = input.param.capacity.cap_res_min.get((cs, y), None)
            temp["out_frac_min"] = input.param.fractions.out_frac_min.get((cs, y), None)
            temp["out_frac_max"] = input.param.fractions.out_frac_max.get((cs, y), None)
            temp["in_frac_min"] = input.param.fractions.in_frac_min.get((cs, y), None)
            temp["in_frac_max"] = input.param.fractions.in_frac_max.get((cs, y), None)
            if any([val is not None for val in temp.values()]):
                param_cs_y[(cs, y)] = Param_CS_Y(**temp, cs=conversion_subprocesses[cs], y=years[y])
    
    param_cs_t = {}
    for cs in conversion_subprocesses:
        for t in times:
            temp = {}
            temp["availability_profile"] = input.param.availability.availability_profile.get((cs, t), None)
            temp["output_profile"] = input.param.output.output_profile.get((cs, t), None)
            if any([val is not None for val in temp.values()]):
                param_cs_t[(cs, t)] = Param_CS_T(**temp, cs=conversion_subprocesses[cs], t=times[t])
    
    return {
        "dataset": {
            "times": times,
            "years": years,
            "commodities": commodities,
            "conversion_processes": conversion_processes,
            "conversion_subprocesses": conversion_subprocesses
        },
        "param": {
            "param_global": param_global,
            "param_cs": param_cs,
            "param_y": param_y,
            "param_cs_y": param_cs_y,
            "param_cs_t": param_cs_t
        }
    }

def write_to_db(db_input, engine) -> None:
    """Write the database to a file."""
    with Session(engine) as session:
        session.add_all(db_input.dataset["times"].values())
        session.add_all(db_input.dataset["years"].values())
        session.add_all(db_input.dataset["commodities"].values())
        session.add_all(db_input.dataset["conversion_processes"].values())
        session.commit()
        # session.add_all(db_input.dataset["conversion_subprocesses"].values())
        session.commit()
        # session.commit()
        # session.add(db_input.dataset["param_global"])
        # session.add_all(db_input.dataset["param_cs"].values())
        # session.add_all(db_input.dataset["param_y"].values())
        # session.add_all(db_input.dataset["param_cs_y"].values())
        # session.add_all(db_input.dataset["param_cs_t"].values())
        session.commit()
        session.close()


