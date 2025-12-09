Генерация картинок через perplexity. Для работы надо в строке 92 указать ваш API_KEY (api_key = "<<YOUR_API_KEY>>")
Пример вызова:
action: pyscript.perplexity_generate_image
data:
  prompt: |
    {{ "Санкт-Петербург, утро, пейзаж" }}
response_variable: perplex

В ответе возвращается:
ok: true
image_url: URL картинки
prompt: Санкт-Петербург, утро, пейзаж
