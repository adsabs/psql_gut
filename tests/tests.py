import random
import sys, os
import time
import itertools

PROJECT_HOME=os.path.join(os.path.dirname(__file__),'..')
sys.path.append(PROJECT_HOME)

from models.models import *

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import testing.postgresql
import unittest

class TestParameters:
  min_users = 1
  max_users = 10**3

  min_groups = 1
  max_groups = 10**2

  min_libraries = 1
  max_libraries = 10**3

  min_tags = 0
  max_tags = 10


class Timer:    
    def __enter__(self):
        self.start = time.clock()
        return self

    def __exit__(self, *args):
        self.end = time.clock()
        self.interval = self.end - self.start

def pprint(string):
  #Centralized place to change output, if so desired in the future
  print string

class Stubdata:
  permissions = [
    {'read':True,'write':False,'public':False},
    {'read':True,'write':True,'public':False},
    {'read':True,'write':False,'public':True},
    {'read':True,'write':True,'public':True},
  ]
    
  tags_colors = ['red','blue','black','green','white','yellow','arbitrary-color-text']
  tags_text = ['good','bad','not-read','read','related','unrelated','arbitrary-tag-text']

  @staticmethod
  def library(fake_bibcode):
    tags = [
             {
               'color':random.choice(Stubdata.tags_colors),
               'text': random.choice(Stubdata.tags_text),
             } for i in range(random.randint(TestParameters.min_tags,TestParameters.max_tags))
           ]

    return {
      'bibcode':'bibcode-%s' % fake_bibcode,
      'tags': tags
      }



class TestModels(unittest.TestCase):
  postgresql = None
  session = None

  @classmethod
  def setUpClass(cls):
    '''
    Sets up a working database with stubdata such that we can perform CRUD testing against it

    -Creates a temporary postgresql instance using testing.postgresql
    -Creates a class-wide session to that instance
    -Creates table-level objects, stored as class attributes
    -Commits each object to the database
    '''

    cls.postgresql = testing.postgresql.Postgresql()
    pprint("postgresql up and running at %s" % cls.postgresql.url())
    engine = create_engine(cls.postgresql.url())
    Base.metadata.create_all(engine)
    cls.session = sessionmaker(bind=engine)()
    
    #Add users
    Users = [User(name='user%s' % i) for i in range(random.randint(TestParameters.min_users,TestParameters.max_users))]
    with Timer() as t:
      [cls.session.add(u) for u in cls.Users]
      cls.session.commit()
    pprint("Committed %s Users in %0.1f seconds" % (len(cls.Users),t.interval))

    #Add groups
    Groups = [Group(name='group%s' % i) for i in range(random.randint(TestParameters.min_groups,TestParameters.max_groups))]
    with Timer() as t:
      [cls.session.add(u) for u in cls.Groups]
      cls.session.commit()
    pprint("Committed %s Groups in %0.1f seconds" % (len(cls.Groups),t.interval))

    #Assign libraries to groups and users based on even/odd numbering

    library_data = [Stubdata.library(i) for i in range(random.randint(TestParameters.min_libraries,TestParameters.max_libraries))]
    with Timer() as t:
      for i,data in enumerate(library_data):
        if i % 2: #If odd number, its a user library
          target=random.choice(Users)
        else:  #If even number, its a group library
          target=random.choice(Groups)
        L = Library(name='library-%s' % i, data=data)
        target.libraries.append(L)
      cls.session.commit()
    pprint("Committed %s Libraries in %0.1f seconds" % (len(cls.Libraries),t.interval))

    #Add users to groups in a probabilistic manner
    for i in range(2):
      for u in Users:
        if random.random() < 0.4:
          continue
        g = random.choice(Groups)
        if g not in u.groups:
          u.groups.append(g)
          #Here is the right place to set permissions
          permission=UserGroupPermission(data=random.choice(Stubdata.permissions))
          permission.group = g
          permission.user = u
    cls.session.commit()

  @classmethod
  def tearDownClass(cls):
    cls.session.close()
    cls.postgresql.stop()

  def setUp(self):
    engine = create_engine(self.__class__.postgresql.url())
    self.session = self.__class__.session

  def tearDown(self):
    self.session.expire_all() #Clears the ORM cache; access on an ORM object performs a new SELECT stmt

  def test_users(self):
    '''
    Assert data are consistent between the psql query and what is stored in the ORM
    '''

    res = self.session.query(User).all()
    self.assertEqual(set([u.name for u in self.Users]),set([u.name for u in res]))
    self.assertEqual(len(self.Users),len(res))

  def test_groups(self):
    '''
    Assert data are consistent between the psql query and what is stored in the ORM
    '''
    res = self.session.query(Group).all()
    self.assertEqual(set([u.name for u in self.Groups]),set([u.name for u in res]))
    self.assertEqual(len(self.Groups),len(res))

  def test_libraries(self):
    '''
    Assert data are consistent between the psql query and what is stored in the ORM
    '''
    user_libraries = [u.libraries for u in self.session.query(User).all()]
    group_libraries = [g.libraries for g in self.session.query(Group).all()]

    all_libraries = list(itertools.chain.from_iterable(user_libraries)) + list(itertools.chain.from_iterable(group_libraries))
    self.assertEqual(len(self.Libraries),len(all_libraries))
    self.assertEqual(set([L.name for L in self.Libraries]),set([L.name for L in all_libraries]))

    all_libraries = self.session.query(Library).all()
    self.assertEqual(len(self.Libraries),len(all_libraries))
    self.assertEqual(set([L.name for L in self.Libraries]),set([L.name for L in all_libraries]))

  def test_convert_userlibrary_to_grouplibrary(self):
    try:
      target_user = next(u for u in self.session.query(User).all() if u.libraries)
    except StopIteration:
      pprint("It seems there is not a single UserLibrary in the database")
      raise

    target_library = next(L for L in target_user.libraries)
    target_user.libraries.remove(target_library)

    try:
      target_group = next(g for g in self.session.query(Group).all() if g.libraries)
    except StopIteration:
      pprint("It seems there is not a single Group in the database")
      raise

    target_group.libraries.append(target_library)


    self.session.expire(target_user)
    self.session.expire(target_library)
    self.session.expire(target_group)

    currently_committed_user = self.session.query(User).filter(User.id==target_user.id).one()
    currently_committed_group = self.session.query(Group).filter(Group.id==target_group.id).one()
    self.assertIn(target_library,currently_committed_user.libraries)
    self.assertNotIn(target_library,currently_committed_group.libraries)

    self.session.commit()

    currently_committed_user = self.session.query(User).filter(User.id==target_user.id).one()
    currently_committed_group = self.session.query(Group).filter(Group.id==target_group.id).one()
    self.assertNotIn(target_library,currently_committed_user.libraries)
    self.assertIn(target_library,currently_committed_group.libraries)


if __name__ == '__main__':
    unittest.main(verbosity=2)



# #Stubdata
# permissions_data = [
#   {'read':True,'write':False,'public':False},
#   {'read':True,'write':True,'public':False},
#   {'read':True,'write':False,'public':True},
#   {'read':True,'write':True,'public':True},]
# colors = ['red','blue','black','green','white','yellow']
# library_data = [[{'bibcode':i,'tag':{'color':random.choice(colors),'text':i}}] for i in range(10**5)]

# #Set up generic users
# _users = [Users(name='user%s' % i) for i in range(10**4)]
# [connection.add(u) for u in _users]

# #Set up generic groups
# _groups = [Groups(name='group%s' % i) for i in range(500)]
# [connection.add(g) for g in _groups]
# connection.commit()


# #Assign libraries to groups and users based on even/odd numbering
# for i,data in enumerate(library_data):
#   if i%2: 
#     target=random.choice(_users)
#     lib = UserLibraries
#   else: 
#     target=random.choice(_groups)
#     lib = GroupLibraries
#   target.libraries.append(lib(name='library-%s' % i, data=data))
# connection.commit()


# #Add users to groups in a probabilistic manner
# for i in range(2):
#   for u in _users:
#     if random.random() < 0.4:
#       continue
#     g = random.choice(_groups)
#     if g not in u.groups:
#       u.groups.append(g)
#       #Here is the right place to set permissions
#       permission=UserGroupPermissions(data=random.choice(permissions_data))
#       u.user_permissions.append(permission)
#       g.group_permissions.append(permission)
# connection.commit()