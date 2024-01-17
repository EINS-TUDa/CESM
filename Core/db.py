from typing import List
from typing import Optional
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

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
    cin: Mapped["Commodity"] = relationship(back_populates="conversion_subprocesses_in")
    cout: Mapped["Commodity"] = relationship(back_populates="conversion_subprocesses_out")
    cp: Mapped["ConversionProcess"] = relationship(back_populates="conversion_subprocesses")

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
    cs: Mapped["ConversionSubprocess"] = relationship(back_populates="param_cs_y")
    y: Mapped["Year"] = relationship(back_populates="param_cs_y")

class Param_CS_T(Base):
    __tablename__ = "param_cs_t"
    id: Mapped[int] = mapped_column(primary_key=True)
    availability_profile: Mapped[float] = mapped_column(nullable=True)
    output_profile: Mapped[float] = mapped_column(nullable=True)
    cs: Mapped["ConversionSubprocess"] = relationship()
    t: Mapped["Time"] = relationship()


# class User(Base):
#     __tablename__ = "user_account"
#     id: Mapped[int] = mapped_column(primary_key=True)
#     name: Mapped[str] = mapped_column(String(30))
#     fullname: Mapped[Optional[str]]
#     addresses: Mapped[List["Address"]] = relationship(
#         back_populates="user", cascade="all, delete-orphan"
#     )


# class Address(Base):
#     __tablename__ = "address"
#     id: Mapped[int] = mapped_column(primary_key=True)
#     email_address: Mapped[str]
#     user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"))
#     user: Mapped["User"] = relationship(back_populates="addresses")
#     def __repr__(self) -> str:
#         return f"Address(id={self.id!r}, email_address={self.email_address!r})"