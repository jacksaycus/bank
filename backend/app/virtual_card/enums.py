from enum import Enum

class VirtualCardStatusEnum(str, Enum):
    Active = "active"
    Inactive = "inactive"
    Pending = "pending"
    Blocked = "blocked"
    Expired = "expired"

class VirtualCardTypeEnum(str, Enum):
    Debit = "debit"
    Credit = "credit"

class VirtualCardBrandEnum(str, Enum):
    Visa = "visa"

class VirtualCardCurrencyEnum(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    KES = "KES"

class CardBlockReasonEnum(str, Enum):
    Lost = "lost"
    Stolen = "stolen"
    Suspicious_Activity = "suspicious_activity"
    Customer_Request = "customer_request"
