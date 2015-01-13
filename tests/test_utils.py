import unittest
from downstream_node import utils

class TestDistribution(unittest.TestCase):
    def setUp(self):
        self.list0 = [10, 10, 20, 20, 30, 30]
        self.list1 = [20, 30]
        self.list2 = [10, 10, 20, 30]
        self.list3 = [10, 10, 20, 20, 20, 30, 30, 30]
        self.dist0 = utils.Distribution(from_list=self.list0)
        self.dist1 = utils.Distribution(from_list=self.list1)
    
    def tearDown(self):
        pass
    
    def test_subtract(self):
        dist2 = self.dist0.subtract(self.dist1)
        self.assertEqual(sorted(dist2.get_list()), sorted(self.list2))
    
    def test_subtract_negative(self):
        dict4 = self.dist1.subtract(self.dist0)
        self.assertEqual(dict4.counts[10], -2)
        self.assertEqual(dict4.counts[20], -1)
        self.assertEqual(dict4.counts[30], -1)
        
    def test_add(self):
        dist3 = self.dist0.add(self.dist1)
        self.assertEqual(sorted(dist3.get_list()), sorted(self.list3))
        
    def test_repr(self):
        self.assertEqual(str(self.dist0), '{10: 2, 20: 2, 30: 2}')
        
    def test_total(self):
        self.assertEqual(sum(self.list0), self.dist0.get_total())

class TestMonopolyDistribution(unittest.TestCase):
    def setUp(self):
        self.distribution_base2 = utils.MonopolyDistribution(1024, 10000, 2)
        self.distribution_base10 = utils.MonopolyDistribution(1000, 100000, 10)
     
    def tearDown(self):
        pass
        
    def distribution_generic_test(self, distribution_object=None):
        if (distribution_object is None):
            return
        dist = distribution_object.get_list()
        possible_chunks = distribution_object.get_possible_chunks()
        
        all_so_far_in = True
        for possibility in possible_chunks:
            if (possibility not in possible_chunks):
                all_so_far_in = False
            else:
                if (all_so_far_in is False):
                    # we are missing a chunk size
                    self.fail('A chunk size was skipped in the distribution')
            
        self.assertLessEqual(sum(dist), distribution_object.total)
        self.assertGreater(sum(dist), distribution_object.total - distribution_object.min)
    
    def test_monopoly_distribution(self):
        # what are we actually trying to accomplish here?
        # we want as wide a range of chunk sizes as possible
        # we also don't want too many of one chunk size
        # ok so what if we have a list of desired chunk sizes
        # just the powers of 10 are simple.  that will be our base
        # with a minimum, obviously.
        # so, total: 25,000
        # min: 100
        # the posibilitites will then be all the powers of 10
        # between 100 and 25,000, or
        # [100, 1000, 10000]
        # the result will be
        # [10000, 1000, 100, 10000, 1000, 100, 1000, 100, 1000, 100, 100, 100, 100, 100, 100, 100]
        # there should not be any skipped values, so it should probably start iterating from the
        # lowest value and then go up to increase the number of chunks
        # the total should be less than the specified total by less than the smallest chunk
        self.distribution_generic_test(self.distribution_base2)
        self.distribution_generic_test(self.distribution_base10)

    def test_get_possible_chunks(self):
        class TestPossibleChunkVector(object):
            def __init__(self, distribution, total, result):
                self.distribution = distribution
                self.total = total
                self.result = result
                
        vectors = [TestPossibleChunkVector(self.distribution_base2, 10000, [1024, 2048, 4096, 8192]),
                   TestPossibleChunkVector(self.distribution_base10, 100000, [1000, 10000])]
    
        for v in vectors:
            self.assertEqual(v.distribution.get_possible_chunks(), v.result)

    def test_get_missing(self):
        fresh = self.distribution_base2.get_list()
        left = fresh.pop(0)
        right = fresh.pop()
        missing = self.distribution_base2.get_missing(fresh).get_list()
        self.assertIn(left, missing)
        self.assertIn(right, missing)
        self.assertEqual(len(missing), 2)
        
        fresh = self.distribution_base10.get_list()
        left = fresh.pop(0)
        right = fresh.pop()
        missing = self.distribution_base10.get_missing(fresh).get_list()
        self.assertIn(left, missing)
        self.assertIn(right, missing)
        self.assertEqual(len(missing), 2)
