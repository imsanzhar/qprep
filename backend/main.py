import random
import jwt
import bcrypt
import httpx
import json
import re
import o
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Dict, List
from fastapi import FastAPI, status, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import engine, Base, get_db
from app.routers import speaking
from models import User, ReadingMaterial, ListeningMaterial, Question, WritingTask, SpeakingTask, TestResult, UserWord
from fastapi import APIRouter, Depends, HTTPException, status
from dotenv import load_dotenv


app = FastAPI(
    title="Q-prep API",
    description="Backend сервер для платформы подготовки к КАЗТЕСТ",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
load_dotenv()
api_key = os.getenv= ("GEMINI_API_KEY")
genai.configure(api_key=api_key)
router = APIRouter(prefix="/api/v1/dictionary", tags=["Dictionary & AI Translation"])
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

class EssayRequest(BaseModel):
    text: str
    task_id: int
    task_type: int
    context: str = ""

class TranslationRequest(BaseModel):
    word: str
    definition: str = ""
    russian: str = ""
    english: str = ""

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
SECRET_KEY = "super-secret-qprep-key-key-for-jwt-authentication-32bytes"
ALGORITHM = "HS256"

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Токен жарамсыз немесе ескірген",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_identifier = payload.get("sub")  # Бұл жерде ID немесе Email болуы мүмкін
        if user_identifier is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    if str(user_identifier).isdigit():
        result = await db.execute(select(User).where(User.id == int(user_identifier)))
    else:
        result = await db.execute(select(User).where(User.email == str(user_identifier)))
        
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user

@router.get("/list")
async def get_user_words(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(UserWord).where(UserWord.user_id == current_user.id))
    words = result.scalars().all()
    words_data = [
        {
            "id": w.id,
            "word": w.word,
            "definition": w.definition,
            "russian": w.russian,
            "english": w.english,
            "next_review": w.next_review.isoformat() if w.next_review else None
        } for w in words
    ]
    return {"success": True, "data": words_data}

@router.post("/add-word")
async def add_custom_word(payload: TranslationRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Проверяем, нет ли уже этого слова у пользователя
    exist_result = await db.execute(
        select(UserWord).where(UserWord.user_id == current_user.id, UserWord.word == payload.word.strip())
    )
    if exist_result.scalars().first():
        return api_response(status_code=400, success=False, message="Бұл сөз сөздігіңізде бұрыннан бар.")

    new_word = UserWord(
        user_id=current_user.id,
        word=payload.word.strip(),
        definition=payload.definition,
        russian=payload.russian,
        english=payload.english or "",
        next_review=datetime.utcnow() # Доступно к повторению сразу
    )
    db.add(new_word)
    await db.commit()
    return api_response(status_code=201, success=True, message="Сөз сәтті қосылды!")

@router.get("/review-cards")
async def get_review_cards(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    now = datetime.utcnow()
    result = await db.execute(
        select(UserWord).where(UserWord.user_id == current_user.id, UserWord.next_review <= now)
    )
    cards = result.scalars().all()
    
    import random
    cards_data = [
        {
            "id": c.id,
            "word": c.word,
            "definition": c.definition,
            "russian": c.russian,
            "english": c.english
        } for c in cards
    ]
    random.shuffle(cards_data)
    
    return {"success": True, "data": cards_data}

@router.post("/assess-review")
async def assess_review(payload: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    word_id = payload.get("word_id")
    remembered = payload.get("remembered") # True или False
    
    result = await db.execute(select(UserWord).where(UserWord.id == word_id, UserWord.user_id == current_user.id))
    word_card = result.scalars().first()
    
    if not word_card:
        raise HTTPException(status_code=404, detail="Карточка табылмады")
        
    # Базовый алгоритм интервалов (в днях или минутах)
    if remembered:
        # Если вспомнил, удваиваем интервал повторения (или переводим на шаг вперед)
        # Для тестов поставим прибавку в часах/днях, например + 1 день
        word_card.next_review = datetime.utcnow() + timedelta(days=1)
    else:
        # Если забыл — возвращаем к повторению очень скоро (через 5 минут)
        word_card.next_review = datetime.utcnow() + timedelta(minutes=5)
        
    await db.commit()
    return api_response(status_code=200, success=True, message="Прогресс сақталды")

@app.post("/api/v1/check-essay")
async def check_essay(data: EssayRequest):
    word_count = len(re.findall(r'\b\w+\b', data.text))

    if data.task_type == 1:
        prompt = f"""
        Сен — ҚАЗТЕСТ (KAZTEST) мемлекеттік жүйесінің Жазылым бөлігін бағалайтын қатаң әрі кәсіби сарапшы емтихан алушысың.
        Оқушы берілген СУРЕТКЕ қарап сипаттама мәтін жазды.
        
        [КОНТЕКСТ] Суретте не бейнеленген (ИИ үшін анықтама): "{data.context}"
        [ОҚУШЫ МӘТІНІ]: "{data.text}"
        [МӘТІНДЕГІ СӨЗ САНЫ]: {word_count} сөз.

        Мәтінді ресми ҚАЗТЕСТ ережесіне сай мына 4 КРИТЕРИЙ бойынша ҚАТАҢ БАҒАЛА (Әр критерий 0-ден 5 баллға дейін, Максимум 20 балл):

        1-Критерий: Ойын жеткізу деңгейі (0-5 балл)
        - 5 балл: Сурет бойынша ойын еркін, жүйелі, айқын жеткізеді. Сөйлемдер логикалық жағынан бір-беримен тығыз байланысқан.
        - 4 балл: Сурет бойынша ойын жеткілікті деңгейде жеткізеді, бірізділік сақталған.
        - 3 балл: Сурет бойынша ойын жалпылама түрде жеткізеді, бірізділік жартылай сақталады.
        - 2-1 балл: Ойы айқын емес, логикалық байланыс нашар немесе мүлдем жоқ.

        2-Критерий: Сөздік қорды пайдалануы (0-5 балл)
        - 5 балл: Сөздік қоры жоғары (50 сөзден жоғары). Орынсыз қайталаулар мен қателер жоқ.
        - 4 балл: Сөздік қоры ортадан жоғары (40-50 сөз).
        - 3 балл: Сөздік қоры орта деңгейде (30-40 сөз).
        - 2-1 балл: Сөздік қоры төмен немесе өте жұтаң (30 сөзден аз).

        3-Критерий: Стилі (0-5 балл)
        - 5 балл: Тіл тазалығы жоғары, стильдік қате мүлдем жоқ немесе тек 1-2 қате кездеседі.
        - 4 балл: 2-3 стильдік қате бар.
        - 3 балл: 4-6 стильдік қате жіберілген.
        - 2-1 балл: 7 немесе одан көп стильдік қате бар.

        4-Критерий: Грамматикалық сауаттылығы (орфографиялық, пунктуациялық) (0-5 балл)
        - 5 балл: Грамматикалық қателер МҮЛДЕМ КЕЗДЕСПЕЙДІ.
        - 4 балл: 1-3 грамматикалық/орфографиялық/пунктуациялық қате бар.
        - 3 балл: 4-7 грамматикалық/пунктуациялық қате жіберілген.
        - 2-1 балл: 8 немесе одан да көп қате жіберілген.
        """
        max_score = 20
    else:
        prompt = f"""
        Сен — ҚАЗТЕСТ (KAZTEST) мемлекеттік жүйесінің Жазылым бөлігін бағалайтын қатаң әрі кәсіби сарапшы емтихан алушысың.
        Оқушы берілген ТАҚЫРЫПҚА эссе жазды.
        
        [ТАҚЫРЫП]: "{data.context}"
        [ОҚУШЫ ЭССЕСІ]: "{data.text}"
        [МӘТІНДЕГІ СӨЗ САНЫ]: {word_count} сөз.

        Мәтінді ресми ҚАЗТЕСТ ережесіне сай мына 3 КРИТЕРИЙ бойынша ҚАТАҢ БАҒАЛА (Әр критерий 0-ден 10 баллға дейін, Максимум 30 балл):

        1-Критерий: Ойын жеткізу деңгейі (0-10 балл)
        - 10-9 балл: Тақырыпты толық ашады. Тезис ұсынып, оны НАҚТЫ ДЕРЕКТЕРМЕН өте жақсы дәлелдейді.
        - 8-7 балл: Тақырыптан ауытқымайды, бірақ дәлелдері (аргументтері) сәл жеткіліксіз.
        - 6-5 балл: Тақырыпты жалпылама береді, аргументтері әлсіз.
        - 4-0 балл: Тақырып ашылмаған, жүйесіз немесе тек 1-2 сөйлеммен шектелген.

        2-Критерий: Сөздік қорды пайдалануы (0-10 балл)
        - 10-9 балл: Сөз байлығы жоғары (~250 сөз). МАҚАЛ-МӘТЕЛДЕРДІ, фразеологизмдерді ұтымды қолданады.
        - 8-7 балл: Сөз баламаларын орынды қолданады (150-200 сөз). Бірақ мақал-мәтел, нақыл сөздер қолданбаған.
        - 6-5 балл: Лексикалық минимумы орта деңгейде (100-150 сөз). Сөздерді жиі қайталайды.
        - 4-0 балл: Сөздік қоры өте төмен, көлемі мүлдем сәйкес келмейді (90 сөзден аз).

        3-Критерий: Грамматикалық сауаттылығы мен стилі (0-10 балл)
        - 10-9 балл: Қателер мүлдем жоқ немесе тек 1-2 жеңіл қате кездеседі.
        - 8-7 балл: Грамматикалық, пунктуациялық не стильдік қателер саны: 3-4 қате.
        - 6-5 балл: Стильдік, пунктуациялық қателер жиілейді (5-7 қате).
        - 4-0 балл: Қарапайым құрылымдардың өзінде қате өте көп, сауаты төмен.
        """
        max_score = 30

    prompt += f"""
    Жауапты ТЕК ҚАНА мынадай қатаң JSON форматында қайтар. Жауапта тек таза JSON болуы тиіс, ешқандай "```json" белгілерін қоспа:
    {{
        "score": (оқушының ресми критерийлер бойынша жинаған нақты балл саны),
        "max_score": {max_score},
        "good_points": "Оқушы жұмысының жетістіктері мен күшті тұстарын ресми критерийлерге сүйене отырып нақты қазақша сипатта.",
        "errors": "Жіберілген қателерді мәтіннен мысал келтіре отырып, нөмірленген тізіммен (1, 2, 3...) және оларды қалай түзету керектігін жаз."
    }}
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json"
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            import asyncio
            response = None
            for attempt in range(3):
                response = await client.post(GEMINI_URL, json=payload, timeout=40.0)
                if response.status_code == 200:
                    break
                elif response.status_code == 503:
                    print(f"503 қате, {attempt+1}-қайталау...")
                    await asyncio.sleep(3)
                else:
                    print(f"Google API Error Content: {response.text}")
                    raise HTTPException(status_code=500, detail="Gemini ИИ сервері жауап бермеді.")
            
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Gemini ИИ сервері жауап бермеді.")
            
            resp_data = response.json()
            raw_text = resp_data['candidates'][0]['content']['parts'][0]['text']
            try:
                result_json = json.loads(raw_text)
                return result_json
            except json.JSONDecodeError as json_err:
                print(f"JSON Parse Error: {json_err}")
                print(f"Raw Gemini Output:\n{raw_text}")
                raise HTTPException(status_code=500, detail="ИИ қайтарған жауап форматы қате.")

        except Exception as e:
            print(f"Толық қате сипаттамасы (Backend): {e}")
            raise HTTPException(status_code=500, detail="Мәтінді ИИ арқылы өңдеу сәтсіз аяқталды.")
        
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(speaking.router)

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd_bytes = plain_password.encode('utf-8')[:72]
    return bcrypt.checkpw(pwd_bytes, hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Токен жарамсыз немесе ескірген. Қайтадан жүйеге кіріңіз.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
        
    return user

def api_response(status_code: int, success: bool, data: dict = None, message: str = "") -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": success,
            "message": message,
            "data": data if data is not None else {}
        }
    )

@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# --- СХЕМЫ PYDANTIC ---

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str = None

class Token(BaseModel):
    access_token: str
    token_type: str

class AnswerModel(BaseModel):
    question_id: int
    answer: str

class TestSubmission(BaseModel):
    reading_answers: List[AnswerModel]
    listening_answers: List[AnswerModel]
    writing_text: str

class SubmitAnswersRequest(BaseModel):
    user_id: int = 1
    material_id: int
    answers: Dict[str, str]

class TranslateRequest(BaseModel):
    word: str


# --- ЭНДПОИНТЫ СИСТЕМЫ ---

@app.get("/", tags=["System"])
async def root_route():
    return api_response(
        status_code=status.HTTP_200_OK,
        success=True,
        message="Добро пожаловать в Q-prep API. Сервер работает в штатном режиме."
    )

@app.get("/api/v1/status", tags=["System"])
async def get_status():
    return api_response(
        status_code=status.HTTP_200_OK,
        success=True,
        data={
            "status": "healthy",
            "database": "connected",
            "version": "1.0.0"
        },
        message="Проверка статуса системы успешно пройдена."
    )

# --- СИДЕР ---

@app.get("/api/v1/seed", tags=["Setup"])
async def seed_all_data(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ReadingMaterial))
    if result.scalars().first():
        return api_response(200, True, message="База данных уже содержит данные. Повторная загрузка не требуется.")
    
    reading = ReadingMaterial(
        title="Қазақстанның табиғаты",
        text_content="Қазақстанның табиғаты өте бай және алуан түрлі. Мұнда биік таулар да, кең далалар да, терең көлдер де бар.",
        level="A2",
        word_count=20
    )
    db.add(reading)
    await db.commit()
    await db.refresh(reading)

    q1 = Question(
        module_type="reading",
        question_text="Мәтін не туралы?",
        option_a="Тарих", option_b="Табиғат", option_c="Экономика", option_d="Спорт",
        correct_option="B",
        reading_material_id=reading.id
    )
    db.add(q1)

    listening = ListeningMaterial(
        title="Астана қаласы",
        audio_url="/assets/audio/test_audio.mp3",
        transcript="Астана - Қазақстанның елордасы. Ол Есіл өзенінің жағасында орналасқан.",
        level="A2"
    )
    db.add(listening)
    await db.commit()
    await db.refresh(listening)

    q2 = Question(
        module_type="listening",
        question_text="Диктор қай қала туралы айтып жатыр?",
        option_a="Алматы", option_b="Астана", option_c="Шымкент", option_d="Тараз",
        correct_option="B",
        listening_material_id=listening.id
    )
    db.add(q2)

    writing = WritingTask(
        title="Эссе: Кітап оқу",
        prompt="«Кітап оқудың пайдасы» тақырыбына шағын эссе жазыңыз.",
        min_words=50,
        level="B1"
    )
    db.add(writing)

    sp_task = SpeakingTask(
        title="Менің болашақ мамандығым",
        prompt="Неліктен осы мамандықты таңдадыңыз? Ония қоғамға пайдасы қандай?",
        prep_time_seconds=60,
        speak_time_seconds=120
    )
    db.add(sp_task)

    await db.commit()
    return api_response(200, True, message="Ура! Барлық тестовый мәліметтер базаға сәтті жүктелді!")


# --- МОДУЛЬДЕР ЭНДПОИНТТЕРІ ---

@app.get("/api/v1/reading/materials", tags=["Reading"])
async def get_reading_materials(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ReadingMaterial))
    materials = result.scalars().all()
    data = [{"id": m.id, "title": m.title, "level": m.level, "word_count": m.word_count} for m in materials]
    return api_response(200, True, data=data)

@app.get("/api/v1/reading/material/{material_id}", tags=["Reading"])
async def get_reading_material(material_id: int, db: AsyncSession = Depends(get_db)):
    mat_result = await db.execute(select(ReadingMaterial).where(ReadingMaterial.id == material_id))
    material = mat_result.scalars().first()
    if not material:
        return api_response(404, False, message="Мәтін табылмады")
    
    q_result = await db.execute(select(Question).where(Question.reading_material_id == material_id, Question.module_type == "reading"))
    questions = q_result.scalars().all()
    q_data = [{
        "id": q.id, "text": q.question_text,
        "options": {"A": q.option_a, "B": q.option_b, "C": q.option_c, "D": q.option_d}
    } for q in questions]

    return api_response(200, True, data={"material": {"id": material.id, "title": material.title, "content": material.text_content}, "questions": q_data})


# --- МОК-ТЕСТ ГЕНЕРАЦИЯСЫ МЕН ТЕКСЕРУ ---

@app.get("/api/v1/mock/generate", tags=["Mock Test"])
async def generate_mock_test(db: AsyncSession = Depends(get_db)):
    reading_result = await db.execute(select(ReadingMaterial))
    all_reading = reading_result.scalars().all()
    
    if not all_reading:
        return api_response(404, False, message="Базада Оқылым материалдары табылмады. Алдымен /seed іске қосыңыз.")
    
    chosen_reading = random.choice(all_reading)
    questions_result = await db.execute(select(Question).where(Question.reading_material_id == chosen_reading.id))
    reading_questions = questions_result.scalars().all()

    listening_result = await db.execute(select(ListeningMaterial))
    all_listening = listening_result.scalars().all()
    chosen_listening = random.choice(all_listening) if all_listening else None
    
    listening_questions = []
    if chosen_listening:
        l_questions_result = await db.execute(select(Question).where(Question.listening_material_id == chosen_listening.id))
        listening_questions = l_questions_result.scalars().all()

    writing_result = await db.execute(select(WritingTask))
    all_writing = writing_result.scalars().all()
    chosen_writing = random.choice(all_writing) if all_writing else None

    test_variant = {
        "reading": {
            "id": chosen_reading.id,
            "title": chosen_reading.title,
            "text": chosen_reading.text_content,
            "questions": [
                {"id": q.id, "text": q.question_text, "options": [q.option_a, q.option_b, q.option_c, q.option_d]}
                for q in reading_questions
            ]
        },
        "listening": {
            "id": chosen_listening.id if chosen_listening else None,
            "title": chosen_listening.title if chosen_listening else "Аудио жүктелмеген",
            "audio_url": chosen_listening.audio_url if chosen_listening else "",
            "questions": [
                {"id": q.id, "text": q.question_text, "options": [q.option_a, q.option_b, q.option_c, q.option_d]}
                for q in listening_questions
            ]
        } if chosen_listening else None,
        "writing": {
            "id": chosen_writing.id if chosen_writing else None,
            "title": chosen_writing.title if chosen_writing else "Тапсырма жоқ",
            "prompt": chosen_writing.prompt if chosen_writing else "",
            "min_words": chosen_writing.min_words if chosen_writing else 50
        } if chosen_writing else None
    }
    return api_response(200, True, data=test_variant, message="Жаңа бірегей Мок-тест нұсқасы сәтті құрастырылды!")

@app.post("/api/v1/mock/submit", tags=["Mock Test"])
async def submit_mock_test(
    submission: TestSubmission, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    score = 0
    total_questions = 0
    
    for ans in submission.reading_answers:
        total_questions += 1
        q_res = await db.execute(select(Question).where(Question.id == ans.question_id))
        question = q_res.scalars().first()
        if question and question.correct_option == ans.answer:
            score += 1
            
    for ans in submission.listening_answers:
        total_questions += 1
        q_res = await db.execute(select(Question).where(Question.id == ans.question_id))
        question = q_res.scalars().first()
        if question and question.correct_option == ans.answer:
            score += 1

    new_result = TestResult(
        user_id=current_user.id,
        module_type="mock",
        score=score,
        max_score=total_questions,
        user_answer=f"Эссе: {submission.writing_text}"
    )
    db.add(new_result)
    await db.commit()
    
    return api_response(
        200, True, 
        data={
            "score": score, 
            "max_score": total_questions, 
            "student": current_user.full_name,
            "message": "Жауаптарыңыз сәтті қабылданды!"
        }, 
        message="Результаты теста успешно обработаны"
    )

@app.post("/api/v1/translate", tags=["Tools"])
async def translate_word(payload: TranslateRequest):
    word = payload.word.lower().strip(',.!?()«»')
    mock_dict = {"ақын": {"ru": "поэт", "en": "poet"}, "білім": {"ru": "знание", "en": "knowledge"}}
    result = mock_dict.get(word, {"ru": "Перевод не найден", "en": "Translation not found"})
    return api_response(200, True, data={"word": word, "translation": result})


# --- АВТОРИЗАЦИЯ ЖӘНЕ ТІРКЕЛУ ---

@app.post("/api/v1/auth/register", tags=["Auth"])
async def register_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Бұл email тіркеліп қойған!")
    
    hashed_password = get_password_hash(user.password)
    new_user = User(email=user.email, hashed_password=hashed_password, full_name=user.full_name)
    
    db.add(new_user)
    await db.commit()
    
    return api_response(200, True, message="Сәтті тіркелдіңіз!")

@app.post("/api/v1/auth/login", response_model=Token, tags=["Auth"])
async def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalars().first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email немесе құпиясөз қате",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/v1/auth/me", tags=["Auth"])
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return {
        "success": True,
        "data": {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email
        }
    }

@app.get("/api/v1/results/my", tags=["Results"])
async def get_my_test_results(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(TestResult)
        .where(TestResult.user_id == current_user.id)
        .order_by(TestResult.id.desc())
    )
    results = result.scalars().all()
    return {
        "success": True,
        "data": [
            {
                "id": r.id,
                "module_type": r.module_type.upper(),
                "score": r.score,
                "max_score": r.max_score,
                "user_answer": r.user_answer
            } for r in results
        ]
    }
@app.get("/api/v1/practice/reading", tags=["Practice"])
async def get_reading_practice(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(ReadingMaterial))
    materials = result.scalars().all()
    
    if not materials:
        raise HTTPException(status_code=404, detail="Базада оқылым материалдары табылмады.")
    
    material = random.choice(materials)
    
    q_result = await db.execute(select(Question).where(Question.reading_material_id == material.id, Question.module_type == "reading"))
    questions = q_result.scalars().all()
    
    return {
        "success": True,
        "data": {
            "id": material.id,
            "title": material.title,
            "text": material.text_content,
            "questions": [
                {
                    "id": q.id,
                    "text": q.question_text,
                    "options": [q.option_a, q.option_b, q.option_c, q.option_d]
                } for q in questions
            ]
        }
    }

app.include_router(router)
