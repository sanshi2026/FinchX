"""Company profile Dataset normalized from Tencent jiankuang.gsjj."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from finchx.contracts import (
    DataStatus,
    Price,
    Provenance,
    ProvenanceClass,
    Quality,
    Source,
    SourceReference,
    StandardRecord,
)
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.fundamental_common import FundamentalRequest, canonical_symbol
from finchx.providers.tencent_f10 import _ProviderF10Payload


class CompanyProfileRequest(FundamentalRequest):
    pass


class CompanyProfileData(ContractModel):
    symbol: str = Field(min_length=1)
    company_name: str | None = Field(default=None, alias="companyName")
    business_description: str | None = Field(default=None, alias="businessDescription")
    issue_price: Price | None = Field(
        default=None,
        alias="issuePrice",
        description="CNY per share. Tencent gsjj.jg is retained as the source candidate.",
    )
    listing_date: date | None = Field(default=None, alias="listingDate")


FUNDAMENTAL_COMPANY_PROFILE_DATASET = DatasetDefinition(
    name="fundamental.company_profile",
    schema_version="1.0",
    request_type=CompanyProfileRequest,
    data_type=CompanyProfileData,
)


def _aware(captured_at: datetime) -> None:
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")


def normalize_company_profile(
    request: CompanyProfileRequest,
    row: _ProviderF10Payload,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(request, CompanyProfileRequest):
        raise ValueError("request must be a CompanyProfileRequest")
    if row.instrument_id != request.instrument_id:
        raise ValueError("provider returned company profile for a different instrument")
    _aware(row.captured_at)
    profile = row.company_profile
    data = CompanyProfileData(
        symbol=canonical_symbol(request.instrument_id),
        companyName=profile.company_name,
        businessDescription=profile.business_description,
        issuePrice=profile.issue_price,
        listingDate=profile.listing_date,
    )
    return StandardRecord(
        dataset=FUNDAMENTAL_COMPANY_PROFILE_DATASET.name,
        schemaVersion=FUNDAMENTAL_COMPANY_PROFILE_DATASET.schema_version,
        recordId=f"{canonical_symbol(request.instrument_id)}@{row.captured_at.isoformat()}",
        entityId=request.instrument_id,
        capturedAt=row.captured_at,
        source=Source(
            providerId=source.provider_id,
            sourceRecordId=row.source_record_id,
            sourceUrl=row.source_url or source.source_url,
        ),
        status=DataStatus.LIVE,
        quality=Quality(),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion="tencent-jiankuang-company-profile-normalizer/1",
            sourceReferences=[
                SourceReference(
                    providerId=source.provider_id,
                    sourceRecordId=row.source_record_id,
                    sourceUrl=row.source_url or source.source_url,
                )
            ],
        ),
        data=data.model_dump(mode="json", by_alias=True),
    )


__all__ = [
    "CompanyProfileData",
    "CompanyProfileRequest",
    "FUNDAMENTAL_COMPANY_PROFILE_DATASET",
    "normalize_company_profile",
]
