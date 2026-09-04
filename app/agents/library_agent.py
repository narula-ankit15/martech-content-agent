from typing import Optional, Union

import shortuuid

from app.models import Channel, ContentLibraryEntry, ContentStatus, EmailDraft, WhatsAppDraft
from app.storage.content_library_store import ContentLibraryStore


class ContentLibraryAgent:
    def __init__(self, store: ContentLibraryStore):
        self._store = store

    def save(
        self,
        *,
        project_id: str,
        campaign_id: str,
        channel: Channel,
        variant_label: str,
        content: Union[EmailDraft, WhatsAppDraft],
        asset_ids: list[str],
        status: ContentStatus = ContentStatus.APPROVED,
        template_name: str = "Untitled Template",
        content_tag: str = "",
    ) -> str:
        # {project_id}-{channel}-{campaign_id}-{shortuuid} keeps IDs
        # human-scannable in the campaign-setup dropdown, per the doc's ID scheme.
        creative_id = f"{project_id}-{channel.value}-{campaign_id}-{shortuuid.ShortUUID().random(length=6)}"
        entry = ContentLibraryEntry(
            creative_id=creative_id,
            project_id=project_id,
            campaign_id=campaign_id,
            channel=channel,
            variant_label=variant_label,
            template_name=template_name,
            template_id=self._store.generate_template_id(channel),
            content_tag=content_tag,
            content_json=content.model_dump(mode="json"),
            asset_ids=asset_ids,
            status=status,
        )
        self._store.save(entry)
        return creative_id

    def delete(self, creative_id: str) -> bool:
        return self._store.delete(creative_id)

    def rename(self, creative_id: str, template_name: str) -> Optional[ContentLibraryEntry]:
        return self._store.rename_template_name(creative_id, template_name)
