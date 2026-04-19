from __future__ import annotations

from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException


class SPAStaticFiles(StaticFiles):
    """Serve the SPA shell for non-asset routes while keeping JS 404s visible."""

    @staticmethod
    def _apply_html_cache_headers(response: Response) -> Response:
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as ex:
            if ex.status_code == 404:
                if path.endswith('.js'):
                    raise ex

                response = await super().get_response('index.html', scope)
                return self._apply_html_cache_headers(response)
            raise ex

        if path in {'', '/', 'index.html'} or response.media_type == 'text/html':
            return self._apply_html_cache_headers(response)

        return response
