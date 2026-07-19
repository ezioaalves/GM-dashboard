import { useState } from "react";
import { assetFileUrl, type LoreAsset } from "../api/lore";

export const UNAVAILABLE_MIRROR_STATES = new Set(["missing_source", "missing_mirror", "failed"]);

export function AssetThumb({ asset, className }: { asset: LoreAsset; className: string }) {
  const [errored, setErrored] = useState(false);
  const canShowImage = !UNAVAILABLE_MIRROR_STATES.has(asset.mirror_state) && !errored;

  if (canShowImage) {
    return (
      <div className={className}>
        <img
          src={assetFileUrl(asset.id)}
          alt={asset.title || asset.source_path}
          loading="lazy"
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
          onError={() => setErrored(true)}
        />
      </div>
    );
  }
  return (
    <div className={className}>
      <span className="mono-inline" style={{ fontSize: 10, color: "var(--text-faint)" }}>
        {asset.asset_type}
        {asset.width && asset.height ? ` · ${asset.width}×${asset.height}` : ""}
      </span>
    </div>
  );
}
