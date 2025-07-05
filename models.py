# c:\Users\sugir\Documents\desktop-app\flet-ocr-app\database.py
# from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
import os

# Define the database file path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'ocr_settings.db')}"

Base = declarative_base()

class Condition(Base):
    __tablename__ = "conditions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)

    data_items = relationship("DataItem", back_populates="condition", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Condition(id={self.id}, name='{self.name}')>"

class DataItem(Base):
    __tablename__ = "data_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    condition_id = Column(Integer, ForeignKey("conditions.id"), nullable=False)

    condition = relationship("Condition", back_populates="data_items")

    def __repr__(self):
        return f"<DataItem(id={self.id}, name='{self.name}', condition_id={self.condition_id})>"

class OcrList(Base):
    __tablename__ = "ocr_lists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)

    uploaded_files = relationship("UploadedFile", back_populates="ocr_list", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<OcrList(id={self.id}, name='{self.name}')>"

class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False) # 元のファイル名
    filepath = Column(String, unique=True, nullable=False) # 保存先の相対パス (images/ocr_list_id/unique_filename)
    filetype = Column(String, nullable=False) # png, jpg, pdfなど
    ocr_list_id = Column(Integer, ForeignKey("ocr_lists.id"), nullable=False)
    is_scanned = Column(Boolean, default=False, nullable=False)
    scanned_at = Column(DateTime, nullable=True)

    ocr_list = relationship("OcrList", back_populates="uploaded_files")
    scanned_data = relationship("ScannedData", back_populates="uploaded_file", cascade="all, delete-orphan")

    def __repr__(self):
        # return f"<UploadedFile(id={self.id}, filename='{self.filename}', ocr_list_id={self.ocr_list_id})>"
        return f"<UploadedFile(id={self.id}, filename='{self.filename}', ocr_list_id={self.ocr_list_id}, is_scanned={self.is_scanned})>"

class ScannedData(Base):
    __tablename__ = "scanned_data"

    id = Column(Integer, primary_key=True, index=True)
    uploaded_file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=False)
    condition_id = Column(Integer, ForeignKey("conditions.id"), nullable=False) # スキャン時に使用した条件
    data_item_name = Column(String, nullable=False) # DataItem.name
    extracted_value = Column(String, nullable=True) # 抽出された値

    uploaded_file = relationship("UploadedFile", back_populates="scanned_data")
    condition = relationship("Condition") # Simple relationship to Condition

    def __repr__(self):
        return f"<ScannedData(id={self.id}, file_id={self.uploaded_file_id}, item='{self.data_item_name}', value='{self.extracted_value[:20]}...')>"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_db_and_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

