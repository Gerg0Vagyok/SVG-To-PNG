#!/usr/bin/env python3
"""
SVG to PNG Converter with True Transparency - Hybrid Approach

Uses browser for JavaScript execution, then Inkscape for transparent rendering.

Requirements:
    pip install selenium pillow

System requirements:
    - Inkscape (install via flatpak(Its assumed its installed))

Alternative fallback to cairosvg:
    pip install cairosvg (Hella broken)

Made By 3 diferent LLMs(ChatGPT, Claude, Gemini). (It does its job IDC ok?)
"""
import os
import sys
import tempfile
import argparse
import time
import subprocess
import shutil
from pathlib import Path
from typing import Optional

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
except ImportError:
    print("Error: selenium is required. Install with: pip install selenium")
    sys.exit(1)

try:
    from PIL import Image
    import io
except ImportError:
    print("Error: Pillow is required. Install with: pip install pillow")
    sys.exit(1)

try:
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False


class SVGToPNGConverter:
    def __init__(self, headless: bool = True, verbose: bool = False): # Added verbose parameter
        self.headless = headless
        self.driver = None
        self.verbose = verbose # Store verbose state

        # REVISED FORCING FLATPAK INKSCAPE START
        if shutil.which("flatpak"):
            self.inkscape_available = True
            if self.verbose: # Conditional print
                print("Detected 'flatpak' command. Will attempt to use Flatpak Inkscape.")
        else:
            self.inkscape_available = False
            print("Error: 'flatpak' command not found. Cannot use Flatpak Inkscape.")
        self.inkscape_app_id = "org.inkscape.Inkscape"
        # REVISED FORCING FLATPAK INKSCAPE END

        # Try to import cairosvg as fallback
        try:
            import cairosvg
            self.cairosvg_available = True
        except ImportError:
            self.cairosvg_available = False

    def _setup_driver(self) -> webdriver.Chrome:
        """Setup Chrome WebDriver."""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--enable-blink-features=CSSColorSchemeUARendering")
        try:
            if WEBDRIVER_MANAGER_AVAILABLE:
                service = Service(ChromeDriverManager().install())
                return webdriver.Chrome(service=service, options=chrome_options)
            return webdriver.Chrome(options=chrome_options)
        except Exception as e:
            raise Exception(f"Chrome setup failed: {e}")

    def _create_html_wrapper(self, svg_content: str, for_export: bool = False) -> str:
        """Create HTML wrapper for SVG processing."""
        if for_export:
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset=\"UTF-8\">
                <style>
                    body {{ margin:0; padding:0; background:transparent; }}
                    svg {{ background:transparent; }}
                </style>
            </head>
            <body>
                {svg_content}
            </body>
            </html>
            """
        else:
            return f"""
            <!DOCTYPE html>
            <html>
            <head><meta charset=\"UTF-8\"></head>
            <body style=\"margin:0;padding:20px\">
                {svg_content}
            </body>
            </html>
            """

    def _extract_processed_svg(self) -> Optional[str]:
        """Extract the processed SVG after JavaScript execution."""
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "svg"))
            )
            time.sleep(2)
            svg_element = self.driver.find_element(By.TAG_NAME, "svg")
            return svg_element.get_attribute('outerHTML')
        except TimeoutException:
            print("Warning: Timeout waiting for SVG")
            return None

    def _process_svg_with_browser(self, svg_content: str) -> str:
        """Use browser to execute JavaScript and return processed SVG."""
        try:
            self.driver = self._setup_driver()
            html_content = self._create_html_wrapper(svg_content)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
                f.write(html_content)
                temp_html = f.name
            try:
                self.driver.get(f"file://{temp_html}")
                processed_svg = self._extract_processed_svg() or svg_content
                return processed_svg
            finally:
                os.unlink(temp_html)
        except Exception as e:
            print(f"Browser processing failed: {e}")
            return svg_content
        finally:
            if self.driver:
                self.driver.quit()

    def _render_with_inkscape(self, svg_content: str, output_path: str,
                               width: Optional[int] = None, height: Optional[int] = None) -> bool:
        """Render SVG to PNG using Inkscape CLI with transparency (via Flatpak)."""
        temp_svg = None
        try:
            cache_dir = Path.home() / ".cache" / "svg_to_png"
            cache_dir.mkdir(parents=True, exist_ok=True)

            with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False, dir=str(cache_dir)) as f:
                f.write(svg_content)
                temp_svg = f.name

            if self.verbose: # Conditional print
                print(f"DEBUG: Created temporary SVG at: {temp_svg}")

            cmd = [
                "flatpak",
                "run",
                "org.inkscape.Inkscape",
                f"--export-filename={output_path}",
                "--export-type=png",
                "--export-background-opacity=0"
            ]

            if width:
                cmd.append(f"--export-width={width}")
            if height:
                cmd.append(f"--export-height={height}")
            cmd.append(temp_svg)

            if self.verbose: # Conditional print
                print(f"DEBUG: Executing Inkscape command: {' '.join(cmd)}")

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                print(f"Inkscape (Flatpak) reported an error (Return Code: {result.returncode}):")
            else:
                if self.verbose: # Conditional print
                    print("Inkscape (Flatpak) reported success (Return Code: 0).")

            if result.stdout:
                if self.verbose: # Conditional print
                    print(f"Inkscape STDOUT:\n{result.stdout.strip()}")
                else:
                    # Always print non-empty stdout if not verbose, just without the "Inkscape STDOUT" label
                    if result.stdout.strip():
                        print(f"{result.stdout.strip()}")
            if result.stderr:
                # Always print stderr, as it's typically for errors/warnings
                print(f"Inkscape STDERR:\n{result.stderr.strip()}")

            if result.returncode == 0:
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    print(f"PNG rendered with Inkscape (Flatpak): {output_path}")
                    return True
                else:
                    print(f"Warning: Inkscape reported success, but output file '{output_path}' is missing or empty.")
                    return False
            else:
                print(f"Inkscape (Flatpak) failed to render PNG.")
                return False
        except FileNotFoundError:
            print(f"Error: 'flatpak' command itself not found. Make sure Flatpak is installed and in your PATH.")
            return False
        except Exception as e:
            print(f"Inkscape rendering error: {e}")
            return False
        finally:
            if temp_svg and os.path.exists(temp_svg):
                try:
                    os.unlink(temp_svg)
                    if self.verbose: # Conditional print
                        print(f"DEBUG: Cleaned up temporary file: {temp_svg}")
                except Exception as e:
                    print(f"Warning: Could not delete temporary file {temp_svg}: {e}")

    def _render_with_cairosvg(self, svg_content: str, output_path: str,
                              width: Optional[int] = None, height: Optional[int] = None) -> bool:
        """Fallback: render with cairosvg (limited filter/mask support)."""
        try:
            import cairosvg
            png_data = cairosvg.svg2png(
                bytestring=svg_content.encode('utf-8'),
                output_width=width,
                output_height=height,
                background_color=None
            )
            with open(output_path, 'wb') as f:
                f.write(png_data)
            print(f"PNG rendered with cairosvg: {output_path}")
            return True
        except Exception as e:
            print(f"cairosvg error: {e}")
            return False

    def convert_svg_to_png(self, svg_content: str, output_path: str,
                             png_width: Optional[int] = None,
                             png_height: Optional[int] = None) -> bool:
        """Convert SVG to PNG with transparency support."""
        if self.verbose: # Conditional print
            print("Stage 1: Processing JavaScript...")
        if '<script>' in svg_content:
            processed_svg = self._process_svg_with_browser(svg_content)
        else:
            if self.verbose: # Conditional print
                print("No JavaScript detected")
            processed_svg = svg_content


        if self.verbose: # Conditional print
            print("Stage 2: Rendering PNG...")
        # Try Inkscape first (now always Flatpak if 'flatpak' command is found)
        if self.inkscape_available:
            if self._render_with_inkscape(processed_svg, output_path, png_width, png_height):
                return True
            print("Inkscape (Flatpak) failed, trying cairosvg...")

        # Fallback to cairosvg
        if self.cairosvg_available:
            return self._render_with_cairosvg(processed_svg, output_path, png_width, png_height)

        print("All rendering methods failed")
        return False

    def convert_svg_file_to_png(self, svg_file_path: str, output_path: str,
                                 png_width: Optional[int] = None,
                                 png_height: Optional[int] = None) -> bool:
        """Convert SVG file to PNG."""
        try:
            with open(svg_file_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            if self.verbose: # Conditional print
                print(f"Reading SVG from: {svg_file_path}")
            return self.convert_svg_to_png(svg_content, output_path, png_width, png_height)
        except FileNotFoundError:
            print(f"Error: SVG file not found: {svg_file_path}")
            return False
        except Exception as e:
            print(f"Error reading SVG file: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="Convert SVG to PNG with transparency")
    parser.add_argument("input", help="Input SVG file path")
    parser.add_argument("output", help="Output PNG file path")
    parser.add_argument("--width", type=int, help="Output PNG width")
    parser.add_argument("--height", type=int, help="Output PNG height")
    parser.add_argument("--open", action="store_true", help="Open the generated PNG file")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output for debugging") # New argument
    args = parser.parse_args()

    converter = SVGToPNGConverter(headless=True, verbose=args.verbose) # Pass verbose to converter
    print("Available renderers:")
    print(f"  - Inkscape (Flatpak): {'✓' if converter.inkscape_available else '✗'}")
    print(f"  - cairosvg: {'✓' if converter.cairosvg_available else '✗'}")
    if not converter.inkscape_available and not converter.cairosvg_available:
        print("\nError: No rendering backends available!")
        print("Ensure 'flatpak' command is in your PATH and Inkscape Flatpak is installed.")
        print("Or install cairosvg: pip install cairosvg")
        sys.exit(1)

    success = converter.convert_svg_file_to_png(
        args.input,
        args.output,
        png_width=args.width,
        png_height=args.height
    )

    if success:
        print("Conversion completed successfully!")
        if args.open:
            import subprocess, platform
            try:
                if platform.system() == "Darwin":
                    subprocess.run(["open", args.output])
                elif platform.system() == "Windows":
                    subprocess.run(["start", args.output], shell=True)
                else:
                    subprocess.run(["xdg-open", args.output])
            except Exception as e:
                print(f"Could not open file: {e}")
    else:
        print("Conversion failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
