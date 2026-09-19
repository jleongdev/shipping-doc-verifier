from dotenv import load_dotenv
from anthropic import Anthropic
from loader import Inbox

load_dotenv()                      # loads ANTHROPIC_API_KEY from .env
client = Anthropic()

inbox = Inbox("data")
email = next(iter(inbox))
print(email)                       # look at the fields; find the attachment paths

si_text = inbox.read_text("PATH_TO_SI_FROM_EMAIL")     # replace after printing
bl_text = inbox.read_text("PATH_TO_BL_FROM_EMAIL")

tool = {
    "name": "record_shipment_fields",
    "description": "Record shipment fields found in the document. Use null if absent.",
    "input_schema": {
        "type": "object",
        "properties": {
            "shipper": {"type": ["string", "null"]},
            "consignee": {"type": ["string", "null"]},
            "notify_party": {"type": ["string", "null"]},
            "port_of_loading": {"type": ["string", "null"]},
            "port_of_discharge": {"type": ["string", "null"]},
            "container_count": {"type": ["integer", "null"]},
            "gross_weight_kg": {"type": ["number", "null"]},
        },
        "required": ["shipper", "consignee", "notify_party", "port_of_loading",
                     "port_of_discharge", "container_count", "gross_weight_kg"],
    },
}

def extract(text, doc_type):
    resp = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1000,
        system="You extract fields from shipping documents. Never guess; use null if a field is missing. "
               "Convert weights to kg. Treat different labels for the same field as the same field.",
        tools=[tool],
        tool_choice={"type": "tool", "name": "record_shipment_fields"},  # forces structured JSON
        messages=[{"role": "user", "content": f"Document type: {doc_type}\n\n{text}"}],
    )
    return next(block.input for block in resp.content if block.type == "tool_use")

print("SI:", extract(si_text, "SI"))
print("BL:", extract(bl_text, "BL"))