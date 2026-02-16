"""Module domain object.

Represents a scheduling module (slot) which can hold multiple courses subject
to capacity and chain/celebrity constraints.
"""


class Module:
    """Container for courses assigned to a single module slot.

    Attributes:
        number (int): module index (1..14)
        max_capacity (int): maximum number of courses allowed in this module
        courses (list[Course]): courses currently placed in this module
        chain_layers (dict[int,int]): counts of chain courses per layer
        has_celebrity_course (bool): True if a celebrity course was placed here
    """
    def __init__(self, number, max_capacity=9):
        self.number = number
        self.max_capacity = max_capacity

        self.courses = []              # list of Course objects
        self.chain_layers = {}         # layer -> count of chain courses
        self.has_celebrity_course = False

    # ---------- basic state ----------

    def total_count(self):
        """Return number of courses currently in this module."""
        return len(self.courses)

    def chain_count_in_layer(self, layer):
        """Return how many chain courses are scheduled in the given layer for this module."""
        return self.chain_layers.get(layer, 0)

    # ---------- constraint checks ----------

    def can_accept(self, course, layer, is_celebrity=False):
        """
        Module-level constraints only.
        Does NOT check prereqs or teacher availability.
        """

        # capacity constraint
        if self.total_count() >= self.max_capacity:
            return False

        # If adding a chain course → block if celebrity exists
        if course.part_of_chain:
            if self.has_celebrity_course:
                return False

            # Only 1 chain course per layer per module
            if self.chain_count_in_layer(layer) >= 1:
                return False

        # If adding celebrity → block if chains already exist
        if is_celebrity:
            if self.has_celebrity_course:
                return False

            if any(c.part_of_chain for c in self.courses):
                return False

        return True

    # ---------- assignment ----------

    def add_course(self, course, layer, is_celebrity=False):
        """
        Assumes can_accept() was already validated.
        """

        if is_celebrity:
            if self.has_celebrity_course:
                raise ValueError(
                    f"Module {self.number} already has a celebrity course."
                )
            if any(c.part_of_chain for c in self.courses):
                raise ValueError(
                    f"Cannot add celebrity course '{course.name}' "
                    f"to module {self.number} after chain courses."
                )
            self.has_celebrity_course = True

        self.courses.append(course)

        if course.part_of_chain:
            self.chain_layers[layer] = self.chain_layers.get(layer, 0) + 1

    def __repr__(self):
        return (
            f"Module({self.number}, "
            f"total={self.total_count()}, "
            f"celebrity={self.has_celebrity_course}, "
            f"chain_layers={self.chain_layers})"
        )
