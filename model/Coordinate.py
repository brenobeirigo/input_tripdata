class Coordinate(object):

    def __init__(self, x, y):
        self.x = x
        self.y = y   

    @classmethod
    def get_middle_point(self, c1, c2):
         # Get middle point of an arrow
        min_x = min([c1.x, c2.x])
        max_x = max([c1.x, c2.x])
        x = min_x + (max_x - min_x) / 2.0
        min_y = min([c1.y, c2.y])
        max_y = max([c1.y, c2.y])
        y = min_y + (max_y - min_y) / 2.0
        return Coordinate(x, y)

    def __str__(self):
        return '<' + str(self.x) + ',' + str(self.y) + '>'

    def __eq__(self, other):
        # First make sure `other` is of the same type
        assert type(other) == type(self)
        # Since `other` is the same type, test if coordinates are equal
        return self.x == other.x and self.y == other.y

    def __repr__(self):
        return 'Coordinate(' + str(self.x) + ',' + str(self.y) + ')'
