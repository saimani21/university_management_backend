from fastapi import FastAPI, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from bson import ObjectId
from typing import List
from random import randint
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
import os
from datetime import datetime, timedelta
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()



origins = [
    "https://unifrontend-c9c8c6c5f499.herokuapp.com",  # Add your frontend app URL here
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Allows CORS for the specified origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)
# MongoDB client setup
# client = AsyncIOMotorClient(
#     "mongodb+srv://saimani21:4410@awsinstances.2sixhn0.mongodb.net/?retryWrites=true&w=majority&appName=awsinstances")
client = AsyncIOMotorClient("mongodb+srv://saimani21:4410@sai.jejgj.mongodb.net/?retryWrites=true&w=majority&appName=Sai")
db = client.university

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "kdsnvjcsnvjnvcdvgdfsjfhcfinifdghdfbvcdifjgbhc")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Security
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Pydantic Models
class User(BaseModel):
    username: str
    password: str
    role: str  # "student", "admin", or "instructor"


class Course(BaseModel):
    course_id: int
    course_name: str
    description: str
    credits: int
    department: str
    fee_per_course: float
    instructor_id: str  # Link to the instructor


class Student(BaseModel):
    student_id: int
    first_name: str
    last_name: str
    email: str
    department: str


class Instructor(BaseModel):
    instructor_id: str
    first_name: str
    last_name: str
    email: str
    department: str


class FeePayment(BaseModel):
    student_id: int
    paid: bool


class Scholarship(BaseModel):
    student_id: int
    amount_awarded: int


class Registration(BaseModel):
    student_id: int
    courses_registered: List[int]



def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    user = await db.users.find_one({"username": username})
    if user is None:
        raise credentials_exception
    return user


# -------------------- User Management --------------------

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await db.users.find_one({"username": form_data.username})
    if not user or not pwd_context.verify(form_data.password, user["password"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user["username"]}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/users")
async def add_user(user: User, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Operation not permitted")

    existing_user = await db.users.find_one({"username": user.username})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_password = pwd_context.hash(user.password)
    user_doc = user.dict()
    user_doc["password"] = hashed_password

    result = await db.users.insert_one(user_doc)
    if result.inserted_id:
        return {"message": "User added successfully", "user_id": str(result.inserted_id)}
    raise HTTPException(status_code=500, detail="Error adding user")


# -------------------- Course Management --------------------

@app.post("/courses")
async def add_course(course: Course, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Operation not permitted")


    while await db.courses.find_one({"course_id": course.course_id}):
        course.course_id = randint(1000, 9999)

    course_doc = course.dict()
    result = await db.courses.insert_one(course_doc)
    if result.inserted_id:
        return {"message": "Course added successfully", "course_id": course.course_id}
    raise HTTPException(status_code=500, detail="Error adding course")


@app.get("/courses")
async def get_courses(current_user: dict = Depends(get_current_user)):
    courses = await db.courses.find().to_list(100)
    for course in courses:
        instructor = await db.instructors.find_one({"instructor_id": course["instructor_id"]})
        course["instructor"] = {
            "first_name": instructor["first_name"],
            "last_name": instructor["last_name"],
            "email": instructor["email"]
        }
    return [{"course_id": course["course_id"],
             "course_name": course["course_name"],
             "description": course["description"],
             "credits": course["credits"],
             "department": course["department"],
             "fee_per_course": course["fee_per_course"],
             "Instructor_details": course["instructor"]} for course in courses]


# -------------------- Student Management --------------------

@app.post("/students")
async def register_student(student: Student, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Operation not permitted")

    while await db.students.find_one({"student_id": student.student_id}):
        student.student_id = randint(10000, 99999)

    student_doc = student.dict()
    result = await db.students.insert_one(student_doc)

    if result.inserted_id:
        # Create registration record for the new student
        registration_doc = Registration(student_id=student.student_id, courses_registered=[])
        await db.registrations.insert_one(registration_doc.dict())
        return {"message": "Student registered successfully", "student_id": student.student_id}

    raise HTTPException(status_code=500, detail="Error registering student")




@app.get("/students")
async def get_students(current_user: dict = Depends(get_current_user)):
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Operation not permitted")

    students = await db.students.find().to_list(100)
    return [{"student_id": student["student_id"],
             "first_name": student["first_name"],
             "last_name": student["last_name"],
             "email": student["email"],
             "department": student["department"],
             } for student in students]


@app.post("/scholarships")
async def award_scholarship(scholarship: Scholarship, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Operation not permitted")

    existing_award = await db.scholarships.find_one({"student_id": scholarship.student_id})
    if existing_award:
        raise HTTPException(status_code=400, detail="Scholarship already awarded to this student")

    scholarship_doc = scholarship.dict()
    result = await db.scholarships.insert_one(scholarship_doc)
    if result.inserted_id:
        return {"message": "Scholarship awarded successfully", "student_id": scholarship.student_id}
    raise HTTPException(status_code=500, detail="Error awarding scholarship")


@app.get("/students/{student_id}/fee")
async def get_fee_info(student_id: int, current_user: dict = Depends(get_current_user)):
    student = await db.students.find_one({"student_id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    registration = await db.registrations.find_one({"student_id": student_id})
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")

    total_fee = sum(course["fee_per_course"] for course in
                    await db.courses.find({"course_id": {"$in": registration["courses_registered"]}}).to_list(100))

    # Check for any scholarship awarded
    scholarship_record = await db.scholarships.find_one({"student_id": student_id})
    scholarship_amount = scholarship_record["amount_awarded"] if scholarship_record else 0

    # Calculate net fee after scholarships
    net_fee = total_fee - scholarship_amount

    return {"student_id": student_id, "total_fee": total_fee, "scholarship awarded": scholarship_amount,
            "net_fee": net_fee}


# -------------------- Registration Management --------------------

@app.put("/students/enroll")
async def enroll_course(student_id: int, course_id: int, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['admin', 'student']:
        raise HTTPException(status_code=403, detail="Operation not permitted")

    student = await db.students.find_one({"student_id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    registration = await db.registrations.find_one({"student_id": student_id})
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")

    result = await db.registrations.update_one(
        {"student_id": student_id},
        {"$addToSet": {"courses_registered": course_id}}
    )
    if result.modified_count == 1:
        return {"message": "Student enrolled successfully"}
    raise HTTPException(status_code=500, detail="Error enrolling in course")


@app.put("/students/drop")
async def drop_course(student_id: int, course_id: int, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['admin', 'student']:
        raise HTTPException(status_code=403, detail="Operation not permitted")

    student = await db.students.find_one({"student_id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    registration = await db.registrations.find_one({"student_id": student_id})
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")

    result = await db.registrations.update_one(
        {"student_id": student_id},
        {"$pull": {"courses_registered": course_id}}
    )
    if result.modified_count == 1:
        return {"message": "Course dropped successfully"}
    raise HTTPException(status_code=500, detail="Error dropping course")


# -------------------- Instructor Management --------------------

@app.post("/instructors")
async def add_instructor(instructor: Instructor, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Operation not permitted")

    instructor_doc = instructor.dict()
    result = await db.instructors.insert_one(instructor_doc)
    if result.inserted_id:
        return {"message": "Instructor added successfully", "instructor_id": instructor.instructor_id}
    raise HTTPException(status_code=500, detail="Error adding instructor")


@app.get("/instructors")
async def get_instructors(current_user: dict = Depends(get_current_user)):
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Operation not permitted")

    instructors = await db.instructors.find().to_list(100)
    return [{"instructor_id": instructor["instructor_id"],
             "first_name": instructor["first_name"],
             "last_name": instructor["last_name"],
             "email": instructor["email"],
             "department": instructor["department"]
             } for instructor in instructors]

@app.get("/courses/{course_id}/students")
async def get_students_in_course(course_id: int, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['admin', 'instructor']:
        raise HTTPException(status_code=403, detail="Operation not permitted")

    # Find all registrations for the specified course
    registrations = await db.registrations.find({"courses_registered": course_id}).to_list(100)
    student_ids = [registration["student_id"] for registration in registrations]

    # Fetch details of the students enrolled in the course
    students = await db.students.find({"student_id": {"$in": student_ids}}).to_list(100)

    return [
        {
            "student_id": student["student_id"],
            "first_name": student["first_name"],
            "last_name": student["last_name"],
            "email": student["email"],
            "department": student["department"]
        } for student in students
    ]





@app.post("/fee_payments")
async def create_fee_record(student_id: int, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Operation not permitted")

    student = await db.registrations.find_one({"student_id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Calculate total fee
    total_fee = sum(course["fee_per_course"] for course in
                    await db.courses.find({"course_id": {"$in": student["courses_registered"]}}).to_list(100))

    # Check for any scholarship awarded
    scholarship_record = await db.scholarships.find_one({"student_id": student_id})
    scholarship_amount = scholarship_record["amount_awarded"] if scholarship_record else 0

    # Calculate net fee after scholarships
    net_fee = total_fee - scholarship_amount

    # Create a fee payment record
    fee_payment_doc = {
        "student_id": student_id,
        "paid": False,  # Initially not paid
        "net_fee": net_fee
    }

    result = await db.fee_payments.insert_one(fee_payment_doc)
    if result.inserted_id:
        return {"message": "Fee payment record created successfully", "net_fee": net_fee}
    raise HTTPException(status_code=500, detail="Error creating fee payment record")

@app.post("/students/{student_id}/pay_fee")
async def pay_fee(student_id: int, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['admin', 'student']:
        raise HTTPException(status_code=403, detail="Operation not permitted")

    student = await db.registrations.find_one({"student_id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Calculate total fee
    total_fee = sum(course["fee_per_course"] for course in await db.courses.find({"course_id": {"$in": student["courses_registered"]}}).to_list(100))

    # Check for any scholarship awarded
    scholarship_record = await db.scholarships.find_one({"student_id": student_id})
    scholarship_amount = scholarship_record["amount_awarded"] if scholarship_record else 0

    # Calculate net fee after scholarships
    net_fee = total_fee - scholarship_amount

    # Update fee payment status
    fee_record = await db.fee_payments.find_one({"student_id": student_id})
    if fee_record:

        if fee_record['paid']:
            return {"message": "Fee already paid", "net_fee": net_fee}

        result = await db.fee_payments.update_one(
            {"student_id": student_id},
            {"$set": {"paid": True, "net_fee": net_fee}}  # Update net_fee in the record
        )
        if result.modified_count == 1:
            return {"message": "Fee payment successful", "net_fee": net_fee}
    else:
        # Create a new fee payment record if it doesn't exist
        fee_payment_doc = {
            "student_id": student_id,
            "paid": True,
            "net_fee": net_fee
        }
        result = await db.fee_payments.insert_one(fee_payment_doc)
        if result.inserted_id:
            return {"message": "Fee payment successful", "net_fee": net_fee}

    raise HTTPException(status_code=500, detail="Error updating fee payment status")



# Run the FastAPI application
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
