import pytest

from api.controllers import ingestion


pytestmark = pytest.mark.functional


def test_ingest_thread_summarizes_and_stores_thread_context(api_client, monkeypatch):
    stored_documents = []

    monkeypatch.setattr(
        ingestion.GeminiDraftingClient,
        "summarize_thread",
        lambda messages: "Mocked thread summary",
    )
    monkeypatch.setattr(
        ingestion.PgVectorContextRepository,
        "store_document",
        lambda thread_id, text: stored_documents.append((thread_id, text)),
    )

    response = api_client.post(
        "/ingest/thread",
        json={
            "thread_id": "thread_1",
            "messages": [
                {"author": "Alice", "text": "Can you send the plan?"},
                {"author": "Bob", "text": "I will send it tomorrow."},
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "thread_id": "thread_1",
        "messages_stored": 2,
    }
    assert len(stored_documents) == 3
    assert stored_documents[0] == ("thread_1", "THREAD SUMMARY:\nMocked thread summary")
    assert stored_documents[1][1].startswith("Message from Alice")
    assert stored_documents[2][1].startswith("Message from Bob")


def test_ingest_thread_accepts_empty_message_list(api_client, monkeypatch):
    called = {"summarized": False, "stored": False}
    monkeypatch.setattr(
        ingestion.GeminiDraftingClient,
        "summarize_thread",
        lambda messages: called.update({"summarized": True}),
    )
    monkeypatch.setattr(
        ingestion.PgVectorContextRepository,
        "store_document",
        lambda thread_id, text: called.update({"stored": True}),
    )

    response = api_client.post("/ingest/thread", json={"thread_id": "thread_1", "messages": []})

    assert response.status_code == 200
    assert response.json()["messages_stored"] == 0
    assert called == {"summarized": False, "stored": False}


def test_ingest_thread_rejects_missing_messages_schema(api_client):
    response = api_client.post("/ingest/thread", json={"thread_id": "thread_1"})

    assert response.status_code == 422


def test_ingest_gmail_thread_fetches_details_and_reuses_thread_ingestion(api_client, monkeypatch):
    monkeypatch.setattr(
        ingestion,
        "get_thread_details",
        lambda thread_id, user_id: {
            "thread_id": "1234567890abcdef",
            "subject": "Project plan",
            "target_email": "owner@example.com",
            "ask_summary": "Send the project plan",
            "messages": [
                {"author": "Alice", "text": "Please send the plan."},
                {"author": "Bob", "text": "Sure."},
            ],
        },
    )
    monkeypatch.setattr(ingestion.GeminiDraftingClient, "summarize_thread", lambda messages: "Summary")
    monkeypatch.setattr(ingestion.PgVectorContextRepository, "store_document", lambda thread_id, text: None)

    response = api_client.post("/ingest/gmail_thread/1234567890abcdef")

    assert response.status_code == 200
    assert response.json()["thread_id"] == "1234567890abcdef"
    assert response.json()["subject"] == "Project plan"
    assert response.json()["target_email"] == "owner@example.com"
    assert response.json()["ask_summary"] == "Send the project plan"
