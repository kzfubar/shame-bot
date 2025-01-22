from todoist.types import Filter

DUE_TODAY = Filter(assigned_self=True) & (Filter("overdue") | Filter("today"))
OVERDUE = Filter(assigned_self=True) & (Filter("overdue"))
SHAME_LABEL = "shame"
