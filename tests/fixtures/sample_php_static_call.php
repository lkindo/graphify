<?php

namespace App\Support;

class StringHelper
{
    public static function slugify(string $text): string
    {
        return strtolower($text);
    }

    public static function truncate(string $text, int $limit): string
    {
        return substr($text, 0, $limit);
    }
}

class SlugGenerator
{
    public function make(string $title): string
    {
        return StringHelper::slugify($title);
    }

    public function shortLabel(string $title): string
    {
        return StringHelper::truncate($title, 20);
    }
}
