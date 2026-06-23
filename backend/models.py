from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class UserWord(Base):
    __tablename__ = "user_words"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    word = Column(String(100), nullable=False)
    definition = Column(String(500), nullable=True)
    russian = Column(String(250), nullable=True)
    english = Column(String(250), nullable=True)
    
    repetitions = Column(Integer, default=0)  # Қайталау саны
    interval = Column(Integer, default=1)     # Келесі қайталауға дейінгі интервал (күн/минут)
    next_review = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

# --- ПОЛЬЗОВАТЕЛИ ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    results = relationship("TestResult", back_populates="user")


# --- ОҚЫЛЫМ (READING) ---
class ReadingMaterial(Base):
    __tablename__ = "reading_materials"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    text_content = Column(Text, nullable=False)
    level = Column(String, index=True)
    word_count = Column(Integer)

    questions = relationship("Question", back_populates="reading_material")


# --- ТЫҢДАЛЫМ (LISTENING) ---
class ListeningMaterial(Base):
    __tablename__ = "listening_materials"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    audio_url = Column(String, nullable=False)
    transcript = Column(Text, nullable=True)
    level = Column(String, index=True)

    questions = relationship("Question", back_populates="listening_material")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    module_type = Column(String, index=True)
    question_text = Column(Text, nullable=False)
    
    option_a = Column(String, nullable=False)
    option_b = Column(String, nullable=False)
    option_c = Column(String, nullable=False)
    option_d = Column(String, nullable=False)
    correct_option = Column(String)
    explanation = Column(Text, nullable=True)

    reading_material_id = Column(Integer, ForeignKey("reading_materials.id"), nullable=True)
    listening_material_id = Column(Integer, ForeignKey("listening_materials.id"), nullable=True)

    reading_material = relationship("ReadingMaterial", back_populates="questions")
    listening_material = relationship("ListeningMaterial", back_populates="questions")


# --- ЖАЗЫЛЫМ (WRITING) ---
class WritingTask(Base):
    __tablename__ = "writing_tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    prompt = Column(Text, nullable=False)
    min_words = Column(Integer, default=50)
    level = Column(String, index=True)


# --- АЙТЫЛЫМ (SPEAKING) ---
class SpeakingTask(Base):
    __tablename__ = "speaking_tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    prompt = Column(Text, nullable=False)
    prep_time_seconds = Column(Integer, default=60)
    speak_time_seconds = Column(Integer, default=120)


# --- РЕЗУЛЬТАТЫ ПОЛЬЗОВАТЕЛЕЙ ---
class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    module_type = Column(String)
    score = Column(Integer, nullable=True)
    max_score = Column(Integer, nullable=True)
    user_answer = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="results")