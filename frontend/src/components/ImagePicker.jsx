// maxImages=1 (WhatsApp's single image_asset_id) swaps the selection on
// click instead of filling up slots -- disabling every other thumbnail
// once one is picked would be a worse single-select UX than letting a
// new click just replace the old pick.
export default function ImagePicker({ assets, selectedIds, onChange, maxImages = 4 }) {
  function toggle(assetId) {
    if (selectedIds.includes(assetId)) {
      onChange(selectedIds.filter((id) => id !== assetId));
      return;
    }
    if (maxImages === 1) {
      onChange([assetId]);
      return;
    }
    if (selectedIds.length < maxImages) {
      onChange([...selectedIds, assetId]);
    }
  }

  if (assets.length === 0) {
    return null;
  }

  const hint =
    maxImages === 1
      ? selectedIds.length === 0
        ? "Optional -- pick one image, or leave blank and the AI will choose."
        : "1 selected -- clear it to let the AI choose instead."
      : selectedIds.length === 0
        ? `Optional -- pick up to ${maxImages} images, or leave blank and the AI will choose. The first pick becomes the main image, the rest appear smaller below it.`
        : `${selectedIds.length} selected -- "Main" is the hero image, the rest appear smaller below it.`;

  return (
    <div className="image-picker">
      <div className="image-picker__grid">
        {assets.map((asset) => {
          const order = selectedIds.indexOf(asset.asset_id);
          const selected = order !== -1;
          return (
            <button
              key={asset.asset_id}
              type="button"
              className={`image-picker__thumb ${selected ? "image-picker__thumb--selected" : ""}`}
              onClick={() => toggle(asset.asset_id)}
              disabled={!selected && maxImages > 1 && selectedIds.length >= maxImages}
              title={
                asset.width && asset.height
                  ? `${asset.width}×${asset.height}${asset.tags?.length ? ` — ${asset.tags.join(", ")}` : ""}`
                  : asset.tags?.join(", ")
              }
            >
              <img src={asset.url} alt="" />
              {asset.width && asset.height && (
                <span className="image-picker__dims">
                  {asset.width}&times;{asset.height}
                </span>
              )}
              {selected && (
                <span className="image-picker__badge">
                  {maxImages === 1 ? "Selected" : order === 0 ? "Main" : order + 1}
                </span>
              )}
            </button>
          );
        })}
      </div>
      <p className="image-picker__hint">{hint}</p>
    </div>
  );
}
