#coding=utf-8
from uuid import uuid4
from datetime import datetime

from pbkdf2 import PBKDF2
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import ( Column, Integer, String,
                        Boolean, DateTime)

from libs.db.dbsession import engine
from libs.db.dbsession import dbSession

Base = declarative_base(engine)



class CmsUsers(Base):

    __tablename__ = 'cms_users'

    uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid4()))
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False)
    email = Column(String(50),unique=True)
    _password = Column('password', String(64))
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime)
    last_login = Column(DateTime)
    loginnum = Column(Integer, default=0)
    _locked = Column(Boolean, default=False, nullable=False)
    avatar = Column(String(128))


    def _hash_password(self, password):
        return PBKDF2.crypt(password, iterations=0x2537)


    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, password):
        self._password = self._hash_password(password)

    def auth_password(self, other_password):
        if self._password:
            return self.password == PBKDF2.crypt(other_password, self.password)
        else:
            return False


    @classmethod
    def all(cls):
        return dbSession.query(cls).all()

    @classmethod
    def by_id(cls, id):
        return dbSession.query(cls).filter(cls.id == id).first()

    @classmethod
    def by_email(cls, email):
        return dbSession.query(cls).filter(cls.email == email).first()

    @classmethod
    def by_uuid(cls, uuid):
        return dbSession.query(cls).filter(cls.uuid == uuid).first()

    @classmethod
    def black_list(cls):
        return dbSession.query(cls).filter(cls._locked == 1).all()

    @classmethod
    def white_list(cls):
        return dbSession.query(cls).filter(cls._locked == 0).all()

    @classmethod
    def by_name(cls, name):
        return dbSession.query(cls).filter(cls.username == name).first()

    @property
    def locked(self):
        return self._locked



    @locked.setter
    def locked(self, value):
        assert isinstance(value, bool)
        self._locked = value


    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'last_login': self.last_login,
        }

    def __repr__(self):
        return u'<CmsUser - id: %s  name: %s>' % (self.id,self.username)