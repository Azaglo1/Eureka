def fragment_requires_app_context():
    raise RuntimeError("This helper fragment must be applied from app.py's create_teaching_plan route.")
