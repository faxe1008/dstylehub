import argparse
import subprocess
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET
from jinja2 import Environment, FileSystemLoader


class DarktableStyle:
    def __init__(self, name: str, description: str, path: Path):
        self.name = name
        self.description = description
        self.path = path

    @staticmethod
    def from_file(path: Path) -> "DarktableStyle":
        tree = ET.parse(path)
        root = tree.getroot()
        info = root.find("info")
        name = info.find("name").text or path.stem
        description = info.find("description").text or ""
        return DarktableStyle(name=name, description=description, path=path)


class Darkroom:
    @staticmethod
    def develop(
        image_path: Path,
        output_base: Path,
        style: Optional[DarktableStyle] = None,
        width: int = 1920,
        quality: int = 80,
    ) -> Path:
        """
        Develops an image and returns the path to the generated .jpg file.
        output_base: path without extension; darktable-cli will append .jpg
        """
        output_base.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "darktable-cli",
            "--import",
            str(image_path.resolve()),
            str(output_base.resolve()),
        ]
        if style:
            cmd.extend(["--style-preset-file", str(style.path.resolve())])
        cmd.extend(
            [
                "--out-ext",
                "jpeg",
                "--width",
                str(width),
                "--core",
                "--conf",
                f"plugins/imageio/format/jpeg/quality={quality}",
            ]
        )
        subprocess.run(
            cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return output_base.with_suffix(".jpg")


def get_output_base_name(original: str, style: Optional[DarktableStyle] = None) -> str:
    safe_base = "".join(c if c.isalnum() else "_" for c in original)
    if style:
        safe_style = "".join(c if c.isalnum() else "_" for c in style.name)
        return f"{safe_style}_{safe_base}"
    return f"developed_{safe_base}"


def main():
    parser = argparse.ArgumentParser(
        description="Generate HTML preview for Darktable styles."
    )
    parser.add_argument(
        "--style-folder", type=Path, required=True, help="Folder with .dtstyle files"
    )
    parser.add_argument(
        "--base-images-folder", type=Path, required=True, help="Folder with base images"
    )
    parser.add_argument(
        "--output-folder",
        type=Path,
        required=True,
        help="Output directory for previews",
    )
    args = parser.parse_args()

    styles = [
        DarktableStyle.from_file(dtpath)
        for dtpath in args.style_folder.glob("*.dtstyle")
    ]

    base_images = list(args.base_images_folder.glob("*.NEF"))
    args.output_folder.mkdir(parents=True, exist_ok=True)

    developed_base = []
    # Develop raw base images
    for img in base_images:
        base_name = img.stem
        output_base = args.output_folder / get_output_base_name(base_name)
        print(f"Developing base image: {img.name}")
        output_file = Darkroom.develop(img, output_base, quality=70)
        developed_base.append(output_file.name)

    # Apply styles
    style_results = {}
    for style in styles:
        results = []
        for img in base_images:
            base_name = img.stem
            output_base = args.output_folder / get_output_base_name(base_name, style)
            print(f"Applying style '{style.name}' to {img.name}")
            output_file = Darkroom.develop(img, output_base, style=style, quality=70)
            results.append(output_file.name)
        style_results[style.name] = results

    # Render HTML
    templates_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template = env.get_template("hub.html.jinja")
    html = template.render(base_images=developed_base, styles=style_results)
    index_file = args.output_folder / "index.html"
    index_file.write_text(html, encoding="utf-8")

    # Copy favicon from templates to output folder
    static_files = ["favicon.png", "favicon_large.png"]
    for static_file in static_files:
        src = templates_dir / static_file
        dest = args.output_folder / static_file
        dest.write_bytes(src.read_bytes())


if __name__ == "__main__":
    main()
