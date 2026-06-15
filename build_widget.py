#!/usr/bin/env python3
"""
Widget Build Script
Minifies and optimizes widget files for production
"""
import hashlib
import os
import re
import gzip
import shutil
from pathlib import Path


def minify_js(content):
    """Basic JavaScript minification"""
    # Remove comments
    content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    # Remove extra whitespace
    content = re.sub(r'\s+', ' ', content)
    content = re.sub(r'\s*([{}();,:])\s*', r'\1', content)
    return content.strip()


def minify_css(content):
    """Basic CSS minification"""
    # Remove comments
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    # Remove extra whitespace
    content = re.sub(r'\s+', ' ', content)
    content = re.sub(r'\s*([{}:;,])\s*', r'\1', content)
    return content.strip()


def minify_html(content):
    """Basic HTML minification"""
    # Remove comments
    content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    # Remove extra whitespace between tags
    content = re.sub(r'>\s+<', '><', content)
    # Minify inline CSS
    def minify_style(match):
        return '<style>' + minify_css(match.group(1)) + '</style>'
    content = re.sub(r'<style>(.*?)</style>', minify_style, content, flags=re.DOTALL)
    return content.strip()


def get_content_hash(content):
    """Generate content hash for cache busting"""
    return hashlib.md5(content.encode()).hexdigest()[:8]


def create_gzip_version(file_path):
    """Create gzipped version of file"""
    with open(file_path, 'rb') as f_in:
        with gzip.open(f"{file_path}.gz", 'wb', compresslevel=9) as f_out:
            shutil.copyfileobj(f_in, f_out)


def build_widget():
    """Build optimized widget files"""
    static_dir = Path("static")
    build_dir = static_dir / "build"
    build_dir.mkdir(exist_ok=True)
    
    # Build loader
    print("Building widget-loader.js...")
    with open(static_dir / "widget-loader.js", "r") as f:
        loader_content = f.read()
    
    # Minify loader
    loader_minified = minify_js(loader_content)
    loader_hash = get_content_hash(loader_minified)
    loader_filename = f"widget-loader.{loader_hash}.js"
    
    with open(build_dir / loader_filename, "w") as f:
        f.write(loader_minified)
    
    # Create gzip version
    create_gzip_version(build_dir / loader_filename)
    
    loader_size = len(loader_content)
    loader_min_size = len(loader_minified)
    loader_gz_size = os.path.getsize(build_dir / f"{loader_filename}.gz")
    
    print(f"  Original: {loader_size:,} bytes")
    print(f"  Minified: {loader_min_size:,} bytes ({100 - loader_min_size*100//loader_size}% reduction)")
    print(f"  Gzipped:  {loader_gz_size:,} bytes ({100 - loader_gz_size*100//loader_size}% total reduction)")
    print(f"  Output:   {loader_filename}")
    
    # Build panel JS
    print("\nBuilding widget-panel.js...")
    with open(static_dir / "widget-panel.js", "r") as f:
        panel_js_content = f.read()
    
    panel_js_minified = minify_js(panel_js_content)
    panel_js_hash = get_content_hash(panel_js_minified)
    panel_js_filename = f"widget-panel.{panel_js_hash}.js"
    
    with open(build_dir / panel_js_filename, "w") as f:
        f.write(panel_js_minified)
    
    create_gzip_version(build_dir / panel_js_filename)
    
    panel_js_size = len(panel_js_content)
    panel_js_min_size = len(panel_js_minified)
    panel_js_gz_size = os.path.getsize(build_dir / f"{panel_js_filename}.gz")
    
    print(f"  Original: {panel_js_size:,} bytes")
    print(f"  Minified: {panel_js_min_size:,} bytes ({100 - panel_js_min_size*100//panel_js_size}% reduction)")
    print(f"  Gzipped:  {panel_js_gz_size:,} bytes ({100 - panel_js_gz_size*100//panel_js_size}% total reduction)")
    print(f"  Output:   {panel_js_filename}")
    
    # Build panel HTML
    print("\nBuilding widget-panel.html...")
    with open(static_dir / "widget-panel.html", "r") as f:
        panel_html_content = f.read()
    
    # Update script reference to use hashed filename
    panel_html_content = panel_html_content.replace(
        '/static/widget-panel.js',
        f'/static/build/{panel_js_filename}'
    )
    
    panel_html_minified = minify_html(panel_html_content)
    panel_html_hash = get_content_hash(panel_html_minified)
    panel_html_filename = f"widget-panel.{panel_html_hash}.html"
    
    with open(build_dir / panel_html_filename, "w") as f:
        f.write(panel_html_minified)
    
    create_gzip_version(build_dir / panel_html_filename)
    
    panel_html_size = len(panel_html_content)
    panel_html_min_size = len(panel_html_minified)
    panel_html_gz_size = os.path.getsize(build_dir / f"{panel_html_filename}.gz")
    
    print(f"  Original: {panel_html_size:,} bytes")
    print(f"  Minified: {panel_html_min_size:,} bytes ({100 - panel_html_min_size*100//panel_html_size}% reduction)")
    print(f"  Gzipped:  {panel_html_gz_size:,} bytes ({100 - panel_html_gz_size*100//panel_html_size}% total reduction)")
    print(f"  Output:   {panel_html_filename}")
    
    # Create manifest file
    manifest = {
        "loader": loader_filename,
        "panel_html": panel_html_filename,
        "panel_js": panel_js_filename,
        "build_timestamp": int(os.path.getmtime(static_dir / "widget-loader.js")),
    }
    
    import json
    with open(build_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    
    print("\n✓ Build complete!")
    print(f"\nTotal sizes (gzipped):")
    print(f"  Loader: {loader_gz_size:,} bytes")
    print(f"  Panel:  {panel_html_gz_size + panel_js_gz_size:,} bytes")
    print(f"  Total:  {loader_gz_size + panel_html_gz_size + panel_js_gz_size:,} bytes")
    
    return manifest


if __name__ == "__main__":
    build_widget()
