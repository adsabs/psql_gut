import os
import sys

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship, sessionmaker, backref
from sqlalchemy import create_engine
from sqlalchemy.ext.associationproxy import association_proxy

Base = declarative_base()

UsersGroups = Table('usersgroups', Base.metadata,
    Column('user_id', Integer, ForeignKey('user.id')),
    Column('group_id', Integer, ForeignKey('group.id'))
)

class User(Base):
  __tablename__='user'
  id = Column(Integer,primary_key=True)
  name = Column(String,nullable=False)

  user_permissions = relationship('UserGroupPermission',backref='user')
  groups = relationship('Group',backref='users',secondary=UsersGroups)
  libraries = relationship('Library',backref='user')

class Group(Base):
  __tablename__ = 'group'
  id = Column(Integer,primary_key=True)
  name = Column(String,nullable=False,unique=True)

  group_permission = relationship('UserGroupPermission',backref='group',uselist=False)
  libraries = relationship('Library',backref='group')

class Library(Base):
  __tablename__ = 'library'
  id = Column(Integer,primary_key=True)
  name = Column(String,nullable=True)
  data = Column(postgresql.JSON,nullable=False)
  user_id = Column(Integer,ForeignKey('user.id'))
  group_id = Column(Integer,ForeignKey('group.id'))

class UserGroupPermission(Base):
  __tablename__='usergrouppermission'
  id = Column(Integer,primary_key=True)
  data = Column(postgresql.JSON,nullable=True)
  user_id = Column(Integer,ForeignKey('user.id'))
  group_id = Column(Integer,ForeignKey('group.id'))