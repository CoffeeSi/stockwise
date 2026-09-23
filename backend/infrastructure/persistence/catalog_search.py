from sqlalchemy import or_


def filter_catalog(query, model, *, active_only: bool, search: str | None):
    if active_only:
        query = query.where(model.is_active.is_(True))
    if search and search.strip():
        term = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(or_(model.code.ilike(f"%{term}%", escape="\\"),
                                model.name.ilike(f"%{term}%", escape="\\")))
    return query
