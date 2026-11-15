# Third-party notices

## Fabrication Gerber connectivity parser

The initial Gerber geometry subset in
`kicad_tooling/hwrepo/fabrication_artwork.py` adapts parser concepts from
`studio-edul/pcb-layout-skill`, `skills/pcb-layout-design/scripts/gerber_check.py`,
commit `62921624db3dffdb0afa097f6b270f68acde3c4d`. The local implementation
has been split into focused modules, narrowed to a fail-closed input subset,
and integrated with this project's typed evidence. The upstream trial source
is not installed or invoked at runtime.

Copyright (c) 2026 studio-edul

MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
