from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

PAGES = ["🏠 Home", "🧑‍🎓 Profile Intake", "🧠 Skill Profile", "🎯 Job Matches", "🔍 Job Details", "🧩 Skill Gaps", "📈 ROI Analysis", "🗺️ Roadmap",
         "📅 Daily Task", "📚 Resources", "📊 Progress", "🤖 Career Copilot", "🔔 Notifications", "🧪 Trust & Accuracy"]


def broken(at):
    return [m.value[:80] for m in at.markdown if "pencil snapped" in m.value]


@pytest.fixture(scope="module")
def app():
    at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=180).run()
    assert not at.exception
    return at


def test_empty_states_render(app):
    for pg in PAGES:
        app.session_state["_goto"] = pg
        app.run()
        assert not app.exception and not broken(app), pg


def test_full_flow_and_every_page(app):
    app.session_state["_goto"] = "🧑‍🎓 Profile Intake"
    app.run()
    app.text_area(key="intake_text").set_value("I'm a Java developer. I've built two Spring Boot projects and know SQL. I haven't worked with Docker. I'm interested in backend development.").run()
    app.button(key="analyze_btn").click().run()
    assert not app.exception and not broken(app)
    for pg in PAGES:
        app.session_state["_goto"] = pg
        app.run()
        assert not app.exception and not broken(app), pg


def test_quiz_flow(app):
    app.session_state["_goto"] = "📅 Daily Task"
    app.run()
    app.button(key="td_qstart").click().run()
    for r in app.radio:
        if r.key and r.key.startswith("qa_"):
            r.set_value(r.options[0])
    app.run()
    [b for b in app.button if "Submit answers" in b.label][0].click().run()
    assert not app.exception and not broken(app)
