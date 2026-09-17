#!/usr/bin/env bash
set -euo pipefail

source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
data_home=${XDG_DATA_HOME:-${HOME:?HOME is not set}/.local/share}
app_dir=$data_home/g600-display-linux
desktop_dir=$data_home/applications
desktop_file=$desktop_dir/g600-display-linux.desktop

for required in G600-Display-for-Linux g600-display-linux.png README.md \
    LICENSE LICENSE_SCOPE.md THIRD_PARTY_NOTICES.md \
    ffmpeg-9.0.1.tar.xz; do
    if [[ ! -f "$source_dir/$required" ]]; then
        echo "Missing $required. Extract the complete release archive first." >&2
        exit 1
    fi
done
if [[ ! -d "$source_dir/third_party" ]]; then
    echo "Missing third_party notices. Extract the complete release archive first." >&2
    exit 1
fi

if [[ "$source_dir" != "$app_dir" ]]; then
    mkdir -p "$app_dir/third_party"
    install -m 755 "$source_dir/G600-Display-for-Linux" "$app_dir/G600-Display-for-Linux"
    install -m 644 "$source_dir/g600-display-linux.png" "$app_dir/g600-display-linux.png"
    for notice in README.md LICENSE LICENSE_SCOPE.md THIRD_PARTY_NOTICES.md \
        ffmpeg-9.0.1.tar.xz 70-g600-display.rules; do
        if [[ -f "$source_dir/$notice" ]]; then
            install -m 644 "$source_dir/$notice" "$app_dir/$notice"
        fi
    done
    cp -a "$source_dir/third_party/." "$app_dir/third_party/"
fi

# Desktop entry Exec values need quoting; percent signs are field-code markers.
exec_path=$app_dir/G600-Display-for-Linux
if [[ "$exec_path" == *$'\n'* || "$exec_path" == *$'\r'* ]]; then
    echo "The install path contains a newline and cannot be used in a desktop shortcut." >&2
    exit 1
fi
escaped_exec=${exec_path//\\/\\\\}
escaped_exec=${escaped_exec//\"/\\\"}
escaped_exec=${escaped_exec//\$/\\\$}
escaped_exec=${escaped_exec//\`/\\\`}
escaped_exec=${escaped_exec//%/%%}

icon_path=$app_dir/g600-display-linux.png
escaped_icon=${icon_path//\\/\\\\}
escaped_icon=${escaped_icon// /\\s}

mkdir -p "$desktop_dir"
cat > "$desktop_file" <<EOF
[Desktop Entry]
Type=Application
Name=G600 Display for Linux
Comment=Unofficial controller for the Shiny Snake G600 display
Exec="$escaped_exec"
Icon=$escaped_icon
Terminal=false
Categories=Utility;
EOF
chmod 755 "$desktop_file"
install -m 755 "$desktop_file" "$app_dir/G600 Display for Linux.desktop"
if [[ "$source_dir" != "$app_dir" && -w "$source_dir" ]]; then
    if install -m 755 "$desktop_file" "$source_dir/G600 Display for Linux.desktop"; then
        echo "The logo shortcut was also added beside the extracted executable."
    else
        echo "Could not add a shortcut to the extracted folder; use the app menu shortcut." >&2
    fi
fi

echo "Installed G600 Display for Linux for this user."
echo "Open it from the app menu, or use the logo shortcut in $app_dir."
