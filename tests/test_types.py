import unittest

from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, PickleType
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from downstream_node.types import MutableTypeWrapper

Base = declarative_base()

class TestObject(object):
    def __init__(self):
        self.item = 0
        
    def add_one(self):
        self.item += 1
    
    def __eq__(self, other):
        return isinstance(other, TestObject) and self.item == other.item
        

class TestModel(Base):
    __tablename__ = 'TestTable'
    
    id = Column(Integer, primary_key=True)
    obj = Column(MutableTypeWrapper.as_mutable(PickleType))



class TestMutableTypeWrapper(unittest.TestCase):
    def setUp(self):
        URI = 'mysql+pymysql://localhost/downstream'
        self.engine = create_engine(URI, echo=True)
        self.engine.execute('DROP TABLE IF EXISTS testtable')
        Base.metadata.create_all(self.engine)
    
    def tearDown(self):
        pass
    
    def test_init_empty(self):
        with self.assertRaises(RuntimeError) as ex:
            wrapper = MutableTypeWrapper(None)
        self.assertEqual(str(ex.exception), 
                         'Unable to create MutableTypeWrapper with no '
                         'underlying object or type.')
    
    def test_init_construct(self):
        wrapper = MutableTypeWrapper(underlying_type=TestObject)
        self.assertIsInstance(wrapper._underlying_object, TestObject)
    
    def test_modify(self):
        Session = sessionmaker(bind=self.engine)
        
        session = Session()
        
        model1 = TestModel(obj=TestObject())
        
        self.assertEqual(model1.obj.item, 0)
        
        session.add(model1)
        session.commit()
        
        self.assertIsInstance(model1.obj, MutableTypeWrapper)
        
        model1.obj.add_one()
        
        session.add(model1)
        session.commit()      
        
        self.assertEqual(model1.obj.item, 1)
        