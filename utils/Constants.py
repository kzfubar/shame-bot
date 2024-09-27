from todoist.types import Filter

DUE_TODAY = Filter(assigned_self=True) & (Filter("overdue") | Filter("today"))
SHAME_LABEL = "shame"
