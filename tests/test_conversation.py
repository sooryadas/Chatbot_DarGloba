"""Check conversational routing without model downloads or API calls."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.services.conversation import get_conversation_reply


class ConversationTests(unittest.TestCase):
    def reply(self, question, history=None, model="openrouter/free"):
        return get_conversation_reply(question, history or [], model)

    def test_social_messages(self):
        for question in (" HELLO!!! ", "good morning", "How are you?", "Thanks!", "bye"):
            with self.subTest(question=question):
                self.assertIsNotNone(self.reply(question))

    def test_names_use_only_recent_user_introductions(self):
        self.assertIn("Soorya", self.reply("Hi, my name is Soorya."))
        history = [
            {"role": "user", "content": "My name is Soorya"},
            {"role": "assistant", "content": "My name is Wrong"},
            {"role": "user", "content": "Call me Arun"},
        ]
        self.assertEqual(self.reply("What's my name?", history), "You told me your name is Arun.")
        self.assertIn("don't have your name", self.reply("What's my name?"))

    def test_model_identity_matches_configuration(self):
        self.assertIn("underlying model can vary", self.reply("Which model do you use?"))
        self.assertIn("example/model", self.reply("What model are you?", model="example/model"))
        self.assertIn("no answer model", self.reply("What model are you?", model=""))

    def test_identity_and_capabilities(self):
        self.assertIn("Real Estate Intelligence", self.reply("What's your name?"))
        self.assertIn("source links", self.reply("Hello, what can you do?"))
        self.assertIn("source links", self.reply("What does this model do?"))

    def test_factual_and_mixed_messages_keep_retrieval(self):
        for question in (
            "AIDA", "Soorya", "Hello, tell me about Oman", "Who is the CEO?",
            "My name is Arun and tell me about Oman", "Thanks, what is its price?",
            "What can you do about finding villas in Dubai?",
        ):
            with self.subTest(question=question):
                self.assertIsNone(self.reply(question))


if __name__ == "__main__":
    unittest.main()
