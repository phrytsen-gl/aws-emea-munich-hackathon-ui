import json
import base64
import boto3
import io
from pdf2image import convert_from_bytes
from PIL.Image import Image, Resampling

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_core.output_parsers import StrOutputParser
from langchain_aws import ChatBedrock
from langchain_aws import AmazonKnowledgeBasesRetriever


def split_pdf_pages(pdf_bytes: bytes, max_size: tuple = (1024, 1024)) -> list[str]:
    images = convert_from_bytes(pdf_file=pdf_bytes, fmt="png")[:20]
    for img in images:
        # resize if it exceeds the max size
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size, Resampling.LANCZOS)

    res = list(map(b64_encoded_str, images))
    return res


def b64_encoded_str(img: Image) -> str:
    byte_io = io.BytesIO()
    img.save(fp=byte_io, format="PNG", quality=75, optimize=True)
    # uncomment the below line, to visualize the image we are sending
    # img.save(f'pdf2img_{str(time.time())}.png') <-- saves the png file
    return base64.b64encode(byte_io.getvalue()).decode("utf8")


def lambda_handler(event, context):
    body = json.loads(event["body"])
    document = base64.decodebytes(body["document"].encode("ascii"))

    client = boto3.client(service_name="bedrock-runtime", region_name="us-west-2")
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"

    sys_prompt = """
    Analyze the given Euro NCAP test document carefully. Follow these steps:

    1. Determine if the document is a valid Euro NCAP document. Look for specific Euro NCAP formatting, terminology, and structure. The document should contain multiple test cases related to vehicle safety assessments.

    2. If the document is valid, extract and list ALL individual tests mentioned. There should be multiple test cases. If you don't find multiple test cases, re-evaluate the document's validity.

    3. For each test, identify:
       a. The exact test name as stated in the document
       b. A brief, factual description of the test's purpose and procedure
       c. Any specific parameters or conditions required to execute the test

    4. Present this information in a structured YAML format.

    5. Do not infer or add any information not explicitly stated in the document. If any required information is not available, use 'N/A' as the value.

    6. If at any point you determine the document is not a valid Euro NCAP test document, set 'is_valid_document' to false and provide a brief explanation in the 'invalid_reason' field.

    Ensure strict adherence to the provided YAML structure in your output.
    Output ONLY a YAML structure without any other text
    Structured Data Format (YAML):
    yamlCopyis_valid_document: boolean
    invalid_reason: string  # Only if is_valid_document is false
    tests:
      - test_name: string
        description: string
        parameters:
          - name: string
            value: string
        """

    base64_encoded_pngs = split_pdf_pages(document)

    model_kwargs = {"anthropic_version": "bedrock-2023-05-31", "max_tokens": 1024}

    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(
            {
                **model_kwargs,
                "system": sys_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            *[
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": base64_encoded_png,
                                    },
                                }
                                for base64_encoded_png in base64_encoded_pngs
                            ],
                        ],
                    }
                ],
            }
        ),
    )

    question = ""
    response_body = json.loads(response.get("body").read())
    for output in response_body.get("content", []):
        question += output["text"]

    template = """Ensure the query is fulfilled by on the following context:
{context}

Discard the query if `is_valid_document` is `false`.

Query: {question}"""

    prompt = ChatPromptTemplate.from_template(template)

    retriever = AmazonKnowledgeBasesRetriever(
        knowledge_base_id="ECSMRBIJWD",  # 👈 Set your Knowledge base ID
        retrieval_config={"vectorSearchConfiguration": {"numberOfResults": 1}},
    )

    model_kwargs = {"anthropic_version": "bedrock-2023-05-31", "max_tokens": 1024}

    model = ChatBedrock(
        client=client,
        model_id=model_id,
        model_kwargs=model_kwargs,
    )

    chain = (
        RunnableParallel({"context": retriever, "question": RunnablePassthrough()})
        .assign(response=prompt | model | StrOutputParser())
        .pick(["response", "context"])
    )

    answer = chain.invoke(question).items()
    for _, value in answer:
        return {
            "statusCode": 200,
            "body": json.dumps(f"{value}\n\nRegulatory Document Extract: {question}"),
        }

    return {
        "statusCode": 200,
        "body": json.dumps("System Architecture is not compliant with the document"),
    }
