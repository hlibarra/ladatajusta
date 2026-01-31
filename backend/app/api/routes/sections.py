"""
API routes for sections (navigation menu)
"""
import uuid
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Section, CategorySectionMapping, Publication
from app.db.session import get_db
from app.api.deps import CurrentAdmin
from pydantic import BaseModel


router = APIRouter()


class SectionBase(BaseModel):
    name: str
    slug: str
    description: str | None = None
    icon: str | None = None
    display_order: int = 0
    is_active: bool = True


class SectionWithCount(SectionBase):
    id: str
    publication_count: int

    class Config:
        from_attributes = True


class SectionListResponse(BaseModel):
    sections: list[SectionWithCount]
    total: int


@router.get("", response_model=SectionListResponse)
async def get_sections(
    db: AsyncSession = Depends(get_db),
    include_inactive: Annotated[bool, Query(description="Include inactive sections")] = False,
) -> Any:
    """
    Get all sections with publication counts.
    Sections are ordered by display_order.
    Only active sections are returned by default.
    """
    # Build query for sections
    query = select(Section).options(selectinload(Section.category_mappings))

    if not include_inactive:
        query = query.where(Section.is_active == True)

    query = query.order_by(Section.display_order)

    result = await db.execute(query)
    sections = result.scalars().all()

    # For each section, count publications
    sections_with_count = []
    for section in sections:
        # Get all category names for this section
        category_names = [mapping.category_name for mapping in section.category_mappings]

        # Count publications with those categories
        if category_names:
            count_query = select(func.count(Publication.id)).where(
                Publication.state == "published",
                Publication.category.in_(category_names)
            )
            count_result = await db.execute(count_query)
            pub_count = count_result.scalar() or 0
        else:
            pub_count = 0

        sections_with_count.append(
            SectionWithCount(
                id=str(section.id),
                name=section.name,
                slug=section.slug,
                description=section.description,
                icon=section.icon,
                display_order=section.display_order,
                is_active=section.is_active,
                publication_count=pub_count,
            )
        )

    return SectionListResponse(
        sections=sections_with_count,
        total=len(sections_with_count),
    )


@router.get("/{slug}/publications", response_model=dict)
async def get_section_publications(
    slug: str,
    db: AsyncSession = Depends(get_db),
    limit: Annotated[int, Query(description="Número de publicaciones", ge=1, le=100)] = 20,
    offset: Annotated[int, Query(description="Offset para paginación", ge=0)] = 0,
) -> Any:
    """
    Get publications for a specific section by slug.
    Returns all publications whose category matches any category mapped to this section.
    """
    # Get section by slug
    section_query = select(Section).where(Section.slug == slug).options(selectinload(Section.category_mappings))
    result = await db.execute(section_query)
    section = result.scalar_one_or_none()

    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    # Get category names for this section
    category_names = [mapping.category_name for mapping in section.category_mappings]

    if not category_names:
        return {
            "section": {
                "id": str(section.id),
                "name": section.name,
                "slug": section.slug,
                "description": section.description,
                "icon": section.icon,
            },
            "publications": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
        }

    # Get publications
    pub_query = (
        select(Publication)
        .where(
            Publication.state == "published",
            Publication.category.in_(category_names)
        )
        .order_by(Publication.published_at.desc())
        .limit(limit)
        .offset(offset)
    )

    pub_result = await db.execute(pub_query)
    publications = pub_result.scalars().all()

    # Count total
    count_query = select(func.count(Publication.id)).where(
        Publication.state == "published",
        Publication.category.in_(category_names)
    )
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Helper function to extract first image URL from media array
    def get_image_url(pub):
        if pub.media:
            for item in pub.media:
                if isinstance(item, dict) and item.get("type") == "image" and item.get("url"):
                    return item["url"]
        return None

    return {
        "section": {
            "id": str(section.id),
            "name": section.name,
            "slug": section.slug,
            "description": section.description,
            "icon": section.icon,
        },
        "publications": [
            {
                "id": str(pub.id),
                "title": pub.title,
                "slug": pub.slug,
                "summary": pub.summary,
                "category": pub.category,
                "tags": pub.tags,
                "image_url": get_image_url(pub),
                "published_at": pub.published_at.isoformat() if pub.published_at else None,
            }
            for pub in publications
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ===== ADMIN ENDPOINTS =====

class SectionCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    icon: str | None = None
    display_order: int = 0
    is_active: bool = True


class SectionUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    icon: str | None = None
    display_order: int | None = None
    is_active: bool | None = None


class CategoryMapping(BaseModel):
    category_name: str


class SectionDetail(SectionWithCount):
    categories: list[str]


@router.post("", response_model=dict)
async def create_section(
    section_data: SectionCreate,
    current_user: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Create a new section.
    Admin only.
    """
    # Check if slug already exists
    existing = await db.execute(
        select(Section).where(Section.slug == section_data.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Section with this slug already exists")

    # Create section
    section = Section(
        name=section_data.name,
        slug=section_data.slug,
        description=section_data.description,
        icon=section_data.icon,
        display_order=section_data.display_order,
        is_active=section_data.is_active,
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)

    return {
        "id": str(section.id),
        "name": section.name,
        "slug": section.slug,
        "message": "Section created successfully"
    }


@router.get("/{section_id}/detail", response_model=SectionDetail)
async def get_section_detail(
    section_id: uuid.UUID,
    current_user: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get section details with categories.
    Admin only.
    """
    result = await db.execute(
        select(Section)
        .where(Section.id == section_id)
        .options(selectinload(Section.category_mappings))
    )
    section = result.scalar_one_or_none()

    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    # Get publication count
    category_names = [mapping.category_name for mapping in section.category_mappings]
    if category_names:
        count_query = select(func.count(Publication.id)).where(
            Publication.state == "published",
            Publication.category.in_(category_names)
        )
        count_result = await db.execute(count_query)
        pub_count = count_result.scalar() or 0
    else:
        pub_count = 0

    return SectionDetail(
        id=str(section.id),
        name=section.name,
        slug=section.slug,
        description=section.description,
        icon=section.icon,
        display_order=section.display_order,
        is_active=section.is_active,
        publication_count=pub_count,
        categories=category_names,
    )


@router.put("/{section_id}", response_model=dict)
async def update_section(
    section_id: uuid.UUID,
    section_data: SectionUpdate,
    current_user: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update a section.
    Admin only.
    """
    result = await db.execute(
        select(Section).where(Section.id == section_id)
    )
    section = result.scalar_one_or_none()

    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    # Update fields
    if section_data.name is not None:
        section.name = section_data.name
    if section_data.slug is not None:
        # Check if new slug conflicts with another section
        if section_data.slug != section.slug:
            existing = await db.execute(
                select(Section).where(
                    Section.slug == section_data.slug,
                    Section.id != section_id
                )
            )
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Slug already in use")
        section.slug = section_data.slug
    if section_data.description is not None:
        section.description = section_data.description
    if section_data.icon is not None:
        section.icon = section_data.icon
    if section_data.display_order is not None:
        section.display_order = section_data.display_order
    if section_data.is_active is not None:
        section.is_active = section_data.is_active

    await db.commit()

    return {
        "id": str(section.id),
        "message": "Section updated successfully"
    }


@router.delete("/{section_id}", response_model=dict)
async def delete_section(
    section_id: uuid.UUID,
    current_user: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Delete a section and its category mappings.
    Admin only.
    """
    result = await db.execute(
        select(Section).where(Section.id == section_id)
    )
    section = result.scalar_one_or_none()

    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    await db.delete(section)
    await db.commit()

    return {"message": "Section deleted successfully"}


@router.post("/{section_id}/categories", response_model=dict)
async def add_category_to_section(
    section_id: uuid.UUID,
    category_data: CategoryMapping,
    current_user: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Add a category mapping to a section.
    Admin only.
    """
    # Check if section exists
    result = await db.execute(
        select(Section).where(Section.id == section_id)
    )
    section = result.scalar_one_or_none()

    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    # Check if mapping already exists
    existing = await db.execute(
        select(CategorySectionMapping).where(
            CategorySectionMapping.section_id == section_id,
            CategorySectionMapping.category_name == category_data.category_name
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Category already mapped to this section")

    # Create mapping
    mapping = CategorySectionMapping(
        section_id=section_id,
        category_name=category_data.category_name,
    )
    db.add(mapping)
    await db.commit()

    return {"message": "Category added to section"}


@router.delete("/{section_id}/categories/{category_name}", response_model=dict)
async def remove_category_from_section(
    section_id: uuid.UUID,
    category_name: str,
    current_user: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Remove a category mapping from a section.
    Admin only.
    """
    await db.execute(
        delete(CategorySectionMapping).where(
            CategorySectionMapping.section_id == section_id,
            CategorySectionMapping.category_name == category_name
        )
    )
    await db.commit()

    return {"message": "Category removed from section"}


@router.get("/admin/available-categories", response_model=list[str])
async def get_available_categories(
    current_user: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get all distinct categories from published publications.
    Admin only.
    """
    result = await db.execute(
        select(Publication.category)
        .where(
            Publication.category.isnot(None),
            Publication.state == "published"
        )
        .distinct()
        .order_by(Publication.category)
    )
    categories = [row[0] for row in result.all()]
    return categories
