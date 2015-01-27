import math


class Distribution(object):

    """Encapsulates a distribution of chunk counts
    """

    def __init__(self, from_counts=None, from_list=None):
        if (from_counts is not None and isinstance(from_counts, dict)):
            self.counts = from_counts
        elif (from_list is not None and isinstance(from_list, list)):
            self.counts = self._counts_from_list(from_list)
        else:
            self.counts = dict()

    def __repr__(self):
        return str(self.counts)

    def _counts_from_list(self, list):
        counts = dict()
        for chunk_size in list:
            counts.setdefault(chunk_size, 0)
            counts[chunk_size] += 1
        return counts

    def get_list(self):
        """Returns a list of all the chunk sizes

        :returns: a list of all the chunk sizes
        """
        dist = list()
        for chunk_size in self.counts.keys():
            dist.extend([chunk_size] * self.counts[chunk_size])
        return dist

    def get_counts(self):
        """Returns a dictionary where the key is the chunk size and the
        value is how many of that size there should be in this distribution

        :returns: the counts of each chunk as a dict
        """
        return self.counts

    def get_total(self):
        """Returns the sum total of chunks"""
        total = 0
        for chunk_size in self.counts.keys():
            total += self.counts[chunk_size] * chunk_size
        return total

    def subtract(self, other):
        """Performs a difference of two distributions by subtracting
        other from self.  i.e. provides a list of items missing in the
        other distribution if self is the ideal distribution.
        :param other: the other distribution to subtract from this one
        :returns: a new distribution
        """
        new = Distribution()
        for c in self.counts.keys():
            new.counts[c] = self.counts[c] - other.counts.get(c, 0)
        for c in other.counts.keys():
            if (c not in self.counts):
                new.counts[c] = -other.counts[c]
        return new

    def add(self, other):
        """Performs a addition of two distributions by adding other to self
        """
        new = Distribution()
        for c in self.counts.keys():
            new.counts[c] = self.counts[c] + other.counts.get(c, 0)
        for c in other.counts.keys():
            if (c not in self.counts):
                new.counts[c] = other.counts[c]
        return new


class MonopolyDistribution(Distribution):

    def __init__(self, min, max, total, base=10):
        Distribution.__init__(self)
        self.base = base
        self.min = min
        self.max = max
        self.total = total
        self._generate_counts()

    def _generate_counts(self):
        possible_chunks = self.get_possible_chunks()
        self.counts = self._generate_distribution_recursive(
            self.total, possible_chunks).get_counts()

    def _generate_distribution_recursive(self, total, possibilities):
        sum_possibilities = sum(possibilities)
        # find out how many of each item we can have
        num_each = total // sum_possibilities

        if (num_each > 0):
            this_count = Distribution(
                from_counts=dict(zip(possibilities,
                                     [num_each] * len(possibilities))))
        else:
            this_count = Distribution()

        # reduce max by the sum contributed by this iteration
        total -= sum_possibilities * num_each
        # pop the largest value, the last one
        possibilities.pop()
        if (total >= self.min and len(possibilities) > 0):
            next_count = self._generate_distribution_recursive(total,
                                                               possibilities)
        else:
            next_count = Distribution()
        return this_count.add(next_count)

    def get_possible_chunks(self):
        """This returns a list of possible chunk sizes within the specified
        range with the given base
        :returns: a list of possible chunk sizes sorted largest to smallest
        """
        # we add self.base to make sure that rounding errors do not cause the
        # floor operation to make n lower than it should be
        n = math.ceil(math.log(self.min, self.base))
        value = int(math.pow(self.base, n))
        unsorted = list()

        while (value < self.max):
            unsorted.append(value)
            n += 1
            value = int(math.pow(self.base, n))

        return sorted(unsorted)

    def get_missing(self, other_list):
        """Alias for subtract... creates a distribution from other_list,
        then subtracts from the self distribution to yield a distribution
        of items that are missing in other_list
        :param other_list: the other list to subtract from self
        :returns: the distribution of missing items
        """
        return self.subtract(Distribution(from_list=other_list))
