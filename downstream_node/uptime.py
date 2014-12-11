
from datetime import datetime, timedelta


class UptimeSummary(object):

    def __init__(self, start=None, end=None, uptime=timedelta(seconds=0)):
        self.start = start
        self.end = end
        self.uptime = uptime

    def fraction(self):
        try:
            return self.uptime.total_seconds() \
                / (self.end - self.start).total_seconds()
        except:
            return 0


class UptimeEvent(object):

    def __init__(self, time, action):
        self.time = time
        self.action = action


class UptimeCalculator(object):

    def __init__(self, uncached, summary=UptimeSummary()):
        self.uncached = uncached
        self.summary = summary
        self.newly_cached = list()

    def update(self):
        """
        Calculates the new summary of uptime from the
        uncached contracts.

        :returns: the new summary
        """
        now = datetime.utcnow()
        events = list()

        for c in self.uncached:
            # iterate through uncached contracts

            # calculate uptime since end of summary
            if (self.summary.end is None or c.start > self.summary.end):
                start = c.start
            else:
                start = self.summary.end

            # until now
            if (c.expiration < now):
                end = c.expiration
                # also, contract is expired
                # we can cache
                self.newly_cached.append(c.id)
            else:
                end = now

            events.append(UptimeEvent(start, 1))
            events.append(UptimeEvent(end, -1))

        # now sort times
        sevents = sorted(events, key=lambda x: x.time)
        # and figure out when the farmer went online and offline since the
        # end of the summary
        count = 0
        elapsed = timedelta(seconds=0)
        start = None
        for event in sevents:
            if (event.action == 1 and count == 0):
                # going online
                start = event.time
            elif (event.action == -1 and count == 1):
                # going offline
                # add elapsed time of this segment
                elapsed += (event.time - start)
            count += event.action

        self.summary.end = now
        self.summary.uptime += elapsed

        return self.summary
