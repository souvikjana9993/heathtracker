# models.py
from pydantic import BaseModel, Field
from typing import Optional

# Complete ReferenceInterval model
class ReferenceInterval(BaseModel):
    """Model for storing reference intervals."""
    normal: Optional[str] = Field(default=None, alias=["Normal","Desirable","Low Risk","Optimal"])
    medium: Optional[str] = Field(default=None, alias=["Borderline","Borderline high","Average Risk","Borderline risk"])
    high: Optional[str] = Field(default=None, alias=["High","Moderate risk"])
    veryhigh: Optional[str] = Field(default=None, alias=["Very High","Undesriable","High risk"])
    other: Optional[str] = Field(default=None, description="Other reference values")

class Parameter(BaseModel):
    """Model for storing a single parameter's result and reference interval."""
    name: str = Field(..., description="Name of the parameter")
    # Change Union type to str to ensure compatibility
    result: str = Field(..., description="Measured result")
    unit: Optional[str] = Field(default=None, description="Unit of measurement")
    reference_interval: ReferenceInterval = Field(..., description="Reference interval")

class MedicalReport(BaseModel):
    """Main model for the entire medical report."""
    patient_name: str = Field(..., description="Name of the patient")
    report_date: str = Field(..., description="Date of the report (YYYY-MM-DD)")
    parameters: list[Parameter] = Field(..., description="List of measured parameters and their reference intervals")