from pydantic import BaseModel, Field, AliasChoices  # <-- Use AliasChoices
from typing import Optional

class ReferenceInterval(BaseModel):
    normal: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("Normal", "Desirable", "Low Risk", "Optimal")
    )
    medium: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("Borderline", "Borderline high", "Average Risk")
    )
    high: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("High", "Moderate risk")
    )
    veryhigh: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("Very High", "Undesirable", "High risk")
    )
    other: Optional[str] = Field(default=None, description="Other reference values")

class Parameter(BaseModel):
    name: str = Field(..., description="Name of the parameter")
    result: str = Field(..., description="Measured result")
    unit: Optional[str] = Field(default=None, description="Unit of measurement")
    reference_interval: ReferenceInterval = Field(..., description="Reference interval")

class MedicalReport(BaseModel):
    patient_name: str = Field(..., description="Name of the patient")
    report_date: str = Field(..., description="Date of the report (YYYY-MM-DD)")
    parameters: list[Parameter] = Field(..., description="List of measured parameters")