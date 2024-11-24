import pytest
from dataclasses import dataclass

from elroy.utils.json_utils import compare_schemas, compare_schemas_with_difflib


@dataclass
class ExpectedSchema:
    name: str
    age: int
    address: Dict[str, str]
    email: str
    generated_schema = {"name": "John Doe", "age": 30, "address": {"street": "123 Main St", "city": "Anytown"}}

    expected_schema = ExpectedSchema(
        name="John Doe",
        age=30,
        address={"street": "123 Main St", "city": "Anytown", "zipcode": "12345"},
        email="john.doe@example.com"
    )

    diff = compare_schemas_with_difflib(generated_schema, expected_schema)
    print(diff)

    discrepancies = compare_schemas(generated_schema, expected_schema)
    assert "Missing key in generated schema: address.zipcode" in discrepancies, "Expected missing zipcode in address"
    assert "Missing key in generated schema: email" in discrepancies, "Expected missing email key"


if __name__ == "__main__":
    pytest.main()
